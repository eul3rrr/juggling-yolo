"""Deterministic frame selection. Estimates are crop hints, never annotations."""
import csv
import math
from scripts.review_track_events import generate_events
from .segments import segment_for_frame, segment_frame_bounds

def load_links(path):
    """Canonical hand associations contain only accepted relations, not candidates."""
    if path is None:
        return []
    with path.open(newline='') as f:
        reader = csv.DictReader(f)
        required = {'source_track_id', 'target_track_id', 'association_type'}
        if not required <= set(reader.fieldnames or []):
            raise ValueError('Expected accepted hand association CSV, not ranked stitch proposals')
        return [dict(row, source_track_id=int(row['source_track_id']), target_track_id=int(row['target_track_id'])) for row in reader if row.get('accepted', 'true').lower() in ('true', '1', 'yes')]

def load_pose(path):
    if path is None:
        return {}
    with path.open(newline='') as f:
        rows = list(csv.DictReader(f))
    result = {}
    for row in rows:
        frame = int(row['frame'])
        if frame not in result or float(row.get('person_confidence', 0)) > float(result[frame].get('person_confidence', 0)):
            result[frame] = row
    return result

def interpolate(a, b, end, start, frame):
    alpha = (frame - end) / (start - end)
    return tuple(((1 - alpha) * x + alpha * y for x, y in zip(a, b)))

def crop_geometry(point, width, height, pose=None):
    """Generous full-frame-coordinate aid; never an object bounding box."""
    x, y = point
    x, y = (min(width, max(0, x)), min(height, max(0, y)))
    points = [(x, y)]
    scale = 0
    if pose:

        def joint(side, name):
            try:
                px, py = (float(pose[f'{side}_{name}_x']), float(pose[f'{side}_{name}_y']))
                conf = float(pose.get(f'{side}_{name}_confidence', 1))
                if conf >= 0.2 and math.isfinite(px + py) and (0 <= px <= width) and (0 <= py <= height):
                    return (px, py)
            except (KeyError, ValueError):
                pass
        wrists = [(side, joint(side, 'wrist')) for side in ('left', 'right')]
        wrists = [(s, p) for s, p in wrists if p]
        if wrists:
            side, _ = min(wrists, key=lambda pair: math.dist(pair[1], (x, y)))
            points += [p for name in ('wrist', 'elbow', 'shoulder') if (p := joint(side, name))]
        try:
            scale = float(pose.get('body_scale_shoulder_px', 0))
            if not math.isfinite(scale):
                scale = 0
        except ValueError:
            pass
    mx, my = (max(width * 0.275, scale * 0.8), max(height * 0.275, scale * 0.8))
    if len(points) == 1:
        cw, ch = (min(width, math.ceil(2 * mx)), min(height, math.ceil(2 * my)))
        left, top = (max(0, min(width - cw, round(x - cw / 2))), max(0, min(height - ch, round(y - ch / 2))))
        return [left, top, left + cw, top + ch]
    return [max(0, math.floor(min((p[0] for p in points)) - mx)), max(0, math.floor(min((p[1] for p in points)) - my)), min(width, math.ceil(max((p[0] for p in points)) + mx)), min(height, math.ceil(max((p[1] for p in points)) + my))]

def mine_candidates(tracks, links, fps, count, width, height, poses=None, segments=None):
    if not math.isfinite(fps) or fps <= 0 or count <= 0:
        raise ValueError('Invalid video metadata')
    poses = poses or {}
    segments = segments or []
    segment_by_frame = {f: segment_for_frame(f, fps, segments) for f in range(count)} if segments else {}
    items = {}

    def add(frame, reason, priority, event, point):
        if not 0 <= frame < count:
            return
        segment = segment_by_frame.get(frame) if segments else None
        if segments and segment is None:
            return
        if segments and any(abs(frame - edge) <= max(1, round(0.1 * fps)) for edge in (round(segment.start * fps), round(segment.end * fps))):
            return
        prov = dict(event)
        prov['distance_from_end'] = frame - event['end_frame'] if event.get('end_frame') is not None else None
        prov['distance_from_start'] = frame - event['start_frame'] if event.get('start_frame') is not None else None
        prov['inside_gap'] = bool(event.get('accepted_link') and event['end_frame'] < frame < event['start_frame'])
        if frame not in items:
            items[frame] = dict(frame=frame, timestamp=frame / fps, priority=priority, reasons=[], provenance=[], focus_point=list(point), crop=crop_geometry(point, width, height, poses.get(frame)), boxes=[], segment=segment.as_dict() if segment else None)
        item = items[frame]
        if priority < item['priority']:
            item.update(priority=priority, focus_point=list(point), crop=crop_geometry(point, width, height, poses.get(frame)))
        if reason not in item['reasons']:
            item['reasons'].append(reason)
        if prov not in item['provenance']:
            item['provenance'].append(prov)
    for row in sorted(links, key=lambda r: (r['source_track_id'], r['target_track_id'])):
        src, dst = (row['source_track_id'], row['target_track_id'])
        if src not in tracks or dst not in tracks:
            raise ValueError('Link references absent track')
        a, b = (tracks[src].last_observed, tracks[dst].first_observed)
        if a is None or b is None or a.frame >= b.frame:
            raise ValueError('Link needs observed, forward boundaries')
        if segments and (segment_for_frame(a.frame, fps, segments) is None or segment_for_frame(b.frame, fps, segments) is None or segment_for_frame(a.frame, fps, segments).index != segment_for_frame(b.frame, fps, segments).index):
            continue
        for key, actual in (('source_end_frame', a.frame), ('target_start_frame', b.frame)):
            if row.get(key) not in (None, '') and int(row[key]) != actual:
                raise ValueError('Link boundary disagrees with observed tracklets')
        ev = dict(event_key=f'linked:{src}:{a.frame}:{dst}:{b.frame}', kind='linked_gap', focus_track_id=src, related_track_id=dst, end_frame=a.frame, start_frame=b.frame, accepted_link=row)
        for t in sorted(set(boundary_frames(a.frame, fps, count) + boundary_frames(b.frame, fps, count) + gap_frames(a.frame, b.frame, fps))):
            point = interpolate((a.center_x, a.center_y), (b.center_x, b.center_y), a.frame, b.frame, min(b.frame, max(a.frame, t)))
            add(t, 'linked_gap', 0, ev, point)
    for e in generate_events(tracks, {}, fps, count):
        kind = 'track_end' if e.kind == 'end' else 'orphan_start'
        if segments and unresolved_event_near_segment_edge(
                e.primary_end_frame, fps, count, segments):
            continue
        ev = dict(event_key=e.event_key, kind=kind, focus_track_id=e.primary.track_id, related_track_id=None, end_frame=e.primary_end_frame if kind == 'track_end' else None, start_frame=e.primary_end_frame if kind == 'orphan_start' else None, accepted_link=None)
        for t in unresolved_boundary_frames(e.primary_end_frame, fps, count):
            add(t, kind, 1, ev, (e.primary_end_x, e.primary_end_y))
    boundaries = [o.frame for tr in tracks.values() for o in (tr.first_observed, tr.last_observed) if o]
    margin = max(1, round(0.25 * fps))
    eligible = {}
    for tid, tr in sorted(tracks.items()):
        observed = {o.frame: o for o in tr.observed}
        for f, o in sorted(observed.items()):
            if f in items or not 0 <= f < count or (segments and segment_by_frame.get(f) is None) or any((abs(f - b) <= margin for b in boundaries)):
                continue
            if all((t in observed for t in range(f - margin, f + margin + 1))):
                eligible.setdefault(f, (tid, o))
    spaced = []
    for f in sorted(eligible):
        if not spaced or f - spaced[-1] >= margin:
            spaced.append(f)
    target = min(len(spaced), max(1, round(len(items) * 0.3 / 0.7)))
    chosen = sorted({spaced[round(i * (len(spaced) - 1) / max(1, target - 1))] for i in range(target)})
    for f in chosen:
        tid, o = eligible[f]
        add(f, 'ordinary', 2, dict(event_key=f'ordinary:{tid}:{f}', kind='ordinary', focus_track_id=None, related_track_id=None, end_frame=None, start_frame=None, accepted_link=None), (o.center_x, o.center_y))
    return sorted(items.values(), key=lambda i: (i['priority'], i['frame']))

def boundary_frames(frame, fps, count):
    offsets = [-15, -9, -6, -4, -2, -1, 0, 1, 2, 4, 6, 9, 15]
    return sorted({frame + round(x * fps / 60) for x in offsets if 0 <= frame + round(x * fps / 60) < count})

def unresolved_boundary_frames(frame, fps, count):
    offsets = [-4, -1, 0, 1, 4]
    return sorted({frame + round(x * fps / 60) for x in offsets
                   if 0 <= frame + round(x * fps / 60) < count})

def unresolved_event_near_segment_edge(frame, fps, count, segments):
    margin = max(1, round(0.2 * fps))
    for segment in segments:
        start, end = segment_frame_bounds(segment, fps, count)
        if start <= frame < end:
            return min(abs(frame - start), abs(frame - end)) <= margin
    return False

def gap_frames(end, start, fps):
    if start - end - 1 <= round(0.2 * fps):
        return list(range(end + 1, start))
    near = max(1, round(fps / 60))
    return sorted({t for t in [end + near, end + 2 * near, start - 2 * near, start - near, *(round(end + (start - end) * q) for q in (0.25, 0.5, 0.75))] if end < t < start})
