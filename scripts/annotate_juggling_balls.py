#!/usr/bin/env python3
"""Mine, annotate locally, export. Never randomly split adjacent video frames."""
import argparse
import hashlib
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.review_track_events import load_tracklets,load_detections,_video_meta
from src.annotation.mining import mine_candidates,load_links,load_pose
from src.annotation.store import Store
from src.annotation.server import make_server
from src.annotation.export import export_yolo


def digest(path):
    with path.open('rb') as f: return hashlib.file_digest(f,'sha256').hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    mine=sub.add_parser('mine',help='Mine existing CSVs without inference')
    for flag in ('video','tracklets'):
        mine.add_argument('--'+flag,type=Path,required=True)
    for flag in ('detections','links','hands'):
        mine.add_argument('--'+flag,type=Path)
    mine.add_argument('--source-group',help='Recording/session/juggler group for future leakage-safe splits')
    serve=sub.add_parser('serve',help='Local annotation UI; default loopback only')
    serve.add_argument('--host',default='127.0.0.1')
    serve.add_argument('--port',type=int,default=43128)
    export=sub.add_parser('export-yolo',help='Completed full frames only; unassigned, never random frame splits')
    export.add_argument('--output',type=Path,required=True)
    for p in (mine,serve,export): p.add_argument('--workspace',type=Path,required=True)
    args=parser.parse_args()
    store=Store(args.workspace)
    if args.command=='mine':
        for key in ('video','tracklets','detections','links','hands'):
            p=getattr(args,key)
            if p and not p.is_file(): parser.error(f'Missing {key}: {p}')
        fps,count,width,height=_video_meta(args.video)
        video_hash=digest(args.video)
        source=dict(source_key=video_hash,video_path=str(args.video.resolve()),fps=fps,
                    frame_count=count,width=width,height=height,source_group=args.source_group or video_hash,
                    inputs={k:dict(path=str(getattr(args,k).resolve()),sha256=digest(getattr(args,k)))
                            for k in ('tracklets','detections','links','hands') if getattr(args,k)})
        candidates=mine_candidates(load_tracklets(args.tracklets),load_links(args.links),fps,count,width,height,load_pose(args.hands))
        detections=load_detections(args.detections) if args.detections else {}
        store.mine(source,candidates,detections)
        counts={name:sum(i['priority']==p for i in candidates) for p,name in enumerate(('linked_gap','unresolved_boundary','ordinary'))}
        reasons={reason:sum(reason in i['reasons'] for i in candidates) for reason in ('linked_gap','track_end','orphan_start','ordinary')}
        print(json.dumps(dict(total=len(candidates),exclusive_priority_counts=counts,overlapping_reasons=reasons),indent=2))
    elif args.command=='serve':
        server=make_server(store,args.host,args.port)
        print(f'Annotation UI: http://{args.host}:{server.server_port}',flush=True)
        try: server.serve_forever()
        except KeyboardInterrupt: pass
        finally: server.server_close()
    else:
        print(f'Exported {export_yolo(store,args.output)} completed full frames to {args.output}')
    return 0


if __name__=='__main__':
    raise SystemExit(main())
