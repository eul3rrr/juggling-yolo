"""Full-frame one-class export. Splits deliberately remain unassigned."""
import json
import os
import shutil
import tempfile
from pathlib import Path
import cv2


def read_frame(source, frame):
    if not 0 <= frame < source['frame_count']: raise ValueError('Frame out of range')
    cap=cv2.VideoCapture(source['video_path'])
    try:
        if not cap.isOpened(): raise ValueError('Cannot open source video')
        cap.set(cv2.CAP_PROP_POS_FRAMES,frame)
        ok,image=cap.read()
        if not ok: raise ValueError('Cannot decode source frame')
        if image.shape[:2] != (source['height'],source['width']): raise ValueError('Source geometry changed')
        return image
    finally: cap.release()


def normalize_box(box,width,height):
    return ((box['x1']+box['x2'])/(2*width),(box['y1']+box['y2'])/(2*height),
            (box['x2']-box['x1'])/width,(box['y2']-box['y1'])/height)


def export_yolo(store, output, frame_reader=read_frame):
    output=Path(output).resolve()
    if output.exists(): raise ValueError('Export output must not exist; choose a new snapshot directory')
    output.parent.mkdir(parents=True,exist_ok=True)
    temp=Path(tempfile.mkdtemp(prefix='.annotation-export-',dir=output.parent))
    try:
        for d in ('images/unassigned','labels/unassigned'): (temp/d).mkdir(parents=True)
        # Consistent read transaction even if the server saves while export runs.
        with store.connection() as c:
            c.execute('BEGIN')
            items=[store.get(r['id'],c) for r in c.execute("SELECT id FROM items WHERE status='completed' ORDER BY source_id,frame")]
        with (temp/'metadata.jsonl').open('w') as metadata:
            for item in items:
                name=item['id']
                image=frame_reader(item['source'],item['frame'])
                if not cv2.imwrite(str(temp/'images/unassigned'/f'{name}.jpg'),image,[cv2.IMWRITE_JPEG_QUALITY,98]):
                    raise ValueError('Image export failed')
                lines=['0 '+' '.join(f'{v:.8f}' for v in normalize_box(b,item['source']['width'],item['source']['height'])) for b in item['boxes']]
                (temp/'labels/unassigned'/f'{name}.txt').write_text('\n'.join(lines)+('\n' if lines else ''))
                metadata.write(json.dumps(dict(item,image=f'images/unassigned/{name}.jpg',split='unassigned'),allow_nan=False)+'\n')
        (temp/'data.yaml').write_text('# Assign train/val by video/session/juggler BEFORE training. Never split adjacent frames randomly.\n'
            '# This is intentionally an unassigned export, not a ready-to-train split.\n'
            'path: '+json.dumps(str(output))+'\nnames:\n  0: juggling_ball\n')
        (temp/'unassigned.txt').write_text(''.join(f'images/unassigned/{i["id"]}.jpg\n' for i in items))
        os.rename(temp,output)
        return len(items)
    except BaseException:
        shutil.rmtree(temp)
        raise
