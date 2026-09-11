"""Transactional SQLite annotations with immutable detector audit and revisions."""
import hashlib
import json
import math
import sqlite3
from contextlib import contextmanager
from pathlib import Path
SURVEY = dict(occluder=['none', 'hand', 'body', 'other_object', 'mixed'], occlusion=['none', 'slight', 'moderate', 'heavy'], visibility=['clear', 'partial', 'tiny_fragment'], motion_blur=['none', 'mild', 'strong'], annotation_confidence=['certain', 'uncertain'])

def stable_id(value):
    return hashlib.sha256(value.encode()).hexdigest()[:24]

def encoded(value):
    return json.dumps(value, sort_keys=True, allow_nan=False)

class Store:

    def __init__(self, workspace):
        self.workspace = Path(workspace).resolve()
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.path = self.workspace / 'annotations.sqlite3'
        with self.connection() as c:
            c.executescript("\n            CREATE TABLE IF NOT EXISTS sources(id TEXT PRIMARY KEY, data TEXT NOT NULL);\n            CREATE TABLE IF NOT EXISTS items(id TEXT PRIMARY KEY, source_id TEXT NOT NULL REFERENCES sources(id),\n                frame INTEGER NOT NULL, priority INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'pending',\n                data TEXT NOT NULL, revision INTEGER NOT NULL DEFAULT 0, UNIQUE(source_id,frame));\n            CREATE TABLE IF NOT EXISTS boxes(id TEXT NOT NULL, item_id TEXT NOT NULL REFERENCES items(id),\n                data TEXT NOT NULL, PRIMARY KEY(item_id,id));\n            CREATE TABLE IF NOT EXISTS predictions(id TEXT PRIMARY KEY, item_id TEXT NOT NULL REFERENCES items(id), data TEXT NOT NULL);\n            CREATE TABLE IF NOT EXISTS saves(id INTEGER PRIMARY KEY, item_id TEXT NOT NULL REFERENCES items(id),\n                revision INTEGER NOT NULL, data TEXT NOT NULL, saved_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);\n            ")

    @contextmanager
    def connection(self):
        c = sqlite3.connect(self.path, timeout=30)
        c.row_factory = sqlite3.Row
        c.execute('PRAGMA foreign_keys=ON')
        try:
            with c:
                yield c
        finally:
            c.close()

    def mine(self, source, candidates, detections):
        sid = stable_id(source['source_key'])
        with self.connection() as c:
            c.execute('BEGIN IMMEDIATE')
            old = c.execute('SELECT data FROM sources WHERE id=?', (sid,)).fetchone()
            if old and json.loads(old['data']) != source:
                raise ValueError('Source metadata/inputs changed: use a new source identity or restore original inputs')
            c.execute('INSERT OR IGNORE INTO sources VALUES (?,?)', (sid, encoded(source)))
            for item in candidates:
                iid = stable_id(source['source_key'] + ':' + str(item['frame']))
                if c.execute('SELECT 1 FROM items WHERE id=?', (iid,)).fetchone():
                    continue
                data = {k: v for k, v in item.items() if k != 'boxes'}
                data.update(focus_status='not_applicable' if item['priority'] == 2 else '', focus_box_id=None, notes='', all_visible_confirmed=False)
                c.execute('INSERT INTO items(id,source_id,frame,priority,data) VALUES (?,?,?,?,?)', (iid, sid, item['frame'], item['priority'], encoded(data)))
                for index, pred in enumerate(detections.get(item['frame'], [])):
                    pid = stable_id(iid + ':prediction:' + str(index))
                    coords = [float(pred[k]) for k in ('x1', 'y1', 'x2', 'y2')]
                    p = dict(id=pid, box=coords, confidence=pred['confidence'])
                    c.execute('INSERT INTO predictions VALUES (?,?,?)', (pid, iid, encoded(p)))
                    x1, y1, x2, y2 = coords
                    if not all((math.isfinite(v) for v in coords)) or not (0 <= x1 < x2 <= source['width'] and 0 <= y1 < y2 <= source['height']):
                        continue
                    b = dict(id=pid, x1=x1, y1=y1, x2=x2, y2=y2, class_name='juggling_ball', annotation_source='preannotation', prediction_id=pid, source_detector_box=coords, source_detector_confidence=pred['confidence'], prediction_status='retained', **{key: '' for key in SURVEY})
                    c.execute('INSERT INTO boxes VALUES (?,?,?)', (pid, iid, encoded(b)))

    def items(self):
        with self.connection() as c:
            return [dict(r) for r in c.execute('SELECT id,source_id,frame,priority,status,revision FROM items ORDER BY priority,source_id,frame')]

    def get(self, iid, connection=None):
        if connection is None:
            with self.connection() as c:
                return self.get(iid, c)
        c = connection
        row = c.execute('SELECT * FROM items WHERE id=?', (iid,)).fetchone()
        if row is None:
            raise ValueError('Unknown annotation item')
        data = json.loads(row['data'])
        data.update(id=iid, source_id=row['source_id'], status=row['status'], revision=row['revision'])
        data['source'] = json.loads(c.execute('SELECT data FROM sources WHERE id=?', (row['source_id'],)).fetchone()['data'])
        data['boxes'] = [json.loads(r['data']) for r in c.execute('SELECT data FROM boxes WHERE item_id=? ORDER BY id', (iid,))]
        kept = {b.get('prediction_id') for b in data['boxes']}
        data['predictions'] = []
        for r in c.execute('SELECT * FROM predictions WHERE item_id=? ORDER BY id', (iid,)):
            prediction = json.loads(r['data'])
            box = next((b for b in data['boxes'] if b.get('prediction_id') == r['id']), None)
            edited = bool(box and [box['x1'], box['y1'], box['x2'], box['y2']] != prediction['box'])
            data['predictions'].append(dict(prediction, deleted=box is None, retained=box is not None, edited=edited, status='deleted' if box is None else ('edited' if edited else 'retained')))
        return data

    def save(self, iid, payload):
        with self.connection() as c:
            c.execute('BEGIN IMMEDIATE')
            old = self.get(iid, c)
            if payload.get('revision') != old['revision']:
                raise ValueError('Stale revision: reload before saving')
            status = payload.get('status')
            if status not in ('pending', 'completed', 'skipped'):
                raise ValueError('Invalid status')
            focus = payload.get('focus_status', '')
            allowed = ('', 'not_applicable') if old['priority'] == 2 else ('', 'visible', 'no_visible_evidence', 'uncertain')
            if focus not in allowed:
                raise ValueError('Invalid focus status')
            boxes = []
            ids = set()
            used_predictions = set()
            predictions = {p['id']: p for p in old['predictions']}
            for raw in payload.get('boxes', []):
                bid = raw.get('id')
                if not isinstance(bid, str) or not bid or len(bid) > 100 or (bid in ids):
                    raise ValueError('Invalid/duplicate box ID')
                ids.add(bid)
                coords = [float(raw[k]) for k in ('x1', 'y1', 'x2', 'y2')]
                x1, y1, x2, y2 = coords
                if not all((math.isfinite(v) for v in coords)) or not (0 <= x1 < x2 <= old['source']['width'] and 0 <= y1 < y2 <= old['source']['height']):
                    raise ValueError('Box must have positive area inside full frame')
                survey = {k: raw.get(k, '') for k in SURVEY}
                if any((v != '' and v not in SURVEY[k] for k, v in survey.items())):
                    raise ValueError('Invalid survey value')
                pid = raw.get('prediction_id')
                if pid and (pid not in predictions or pid in used_predictions):
                    raise ValueError('Invalid detector prediction relation')
                if pid:
                    used_predictions.add(pid)
                pred = predictions.get(pid)
                prediction_status = None
                if pred:
                    prediction_status = 'retained' if [x1, y1, x2, y2] == pred['box'] else 'edited'
                boxes.append(dict(id=bid, x1=x1, y1=y1, x2=x2, y2=y2, class_name='juggling_ball', **survey, annotation_source='preannotation' if pred else 'manual', prediction_id=pid if pred else None, prediction_status=prediction_status, source_detector_confidence=pred['confidence'] if pred else None, source_detector_box=pred['box'] if pred else None))
            focus_box = payload.get('focus_box_id') or None
            if focus_box and (focus != 'visible' or focus_box not in ids):
                raise ValueError('Invalid focus box')
            data = {k: old[k] for k in ('frame', 'timestamp', 'priority', 'reasons', 'provenance', 'crop', 'focus_point')}
            data.update(focus_status=focus, focus_box_id=focus_box, notes=str(payload.get('notes', ''))[:10000], all_visible_confirmed=payload.get('all_visible_confirmed') is True)
            c.execute('UPDATE items SET status=?,data=?,revision=revision+1 WHERE id=?', (status, encoded(data), iid))
            c.execute('DELETE FROM boxes WHERE item_id=?', (iid,))
            c.executemany('INSERT INTO boxes VALUES (?,?,?)', [(b['id'], iid, encoded(b)) for b in boxes])
            c.execute('INSERT INTO saves(item_id,revision,data) VALUES (?,?,?)', (iid, old['revision'] + 1, encoded(dict(data, status=status, boxes=boxes))))
        return self.get(iid)
