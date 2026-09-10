#!/usr/bin/env python3
"""Mine, annotate locally, export. Never randomly split adjacent video frames."""
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.review_track_events import load_tracklets, load_detections, _video_meta
from src.annotation.mining import mine_candidates, load_links, load_pose
from src.annotation.segments import parse_losslesscut_csv, pair_video_segments, discover_pairs, discover_video_files
from src.annotation.store import Store
from src.annotation.server import make_server
from src.annotation.export import export_yolo

def digest(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

def safe_name(value):
    return ''.join(c if c.isalnum() or c in '._-' else '-' for c in value).strip('-')

def prepare_sources(args):
    if args.batch_size <= 0:
        raise ValueError('--batch-size must be positive')
    root = args.output_root.expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    try:
        tool_commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        tool_commit = 'unknown'
    failures = 0
    prepared = skipped = 0
    for video, segment_path in discover_pairs(args.source_dir):
        out = None
        try:
            fps, count, width, height = _video_meta(video)
            segments = parse_losslesscut_csv(segment_path, duration=count / fps)
            video_sha = digest(video)
            segment_sha = digest(segment_path)
            source_id = safe_name(video.stem) + '-' + video_sha[:12]
            out = root / source_id
            config = dict(model=args.model, conf=args.conf, imgsz=args.imgsz, classes=args.classes, device=args.device, batch_size=args.batch_size, distance_threshold=args.distance_threshold, hit_counter_max=args.hit_counter_max)
            expected = dict(video_path=str(video.resolve()), video_sha256=video_sha, segments_path=str(segment_path.resolve()), segments_sha256=segment_sha, segments=[s.as_dict() for s in segments], config=config, tool_commit=tool_commit)
            manifest_path = out / 'manifest.json'
            if not args.force and manifest_path.is_file() and (out / 'detections.csv').is_file() and (out / 'tracklets.csv').is_file():
                existing = json.loads(manifest_path.read_text())
                if all(existing.get(k) == v for k, v in expected.items()):
                    print(f'{video.name}: already prepared')
                    skipped += 1
                    continue
                raise ValueError('existing preprocessing manifest differs; rerun with --force')
            if out.exists() and not args.force:
                raise ValueError('preprocessing output exists without a matching manifest; rerun with --force')
            if args.force and out.exists():
                shutil.rmtree(out)
            out.mkdir(parents=True, exist_ok=True)
            detections = out / 'detections.csv'
            tracklets = out / 'tracklets.csv'
            base = [sys.executable]
            subprocess.run(base + [str(ROOT / 'scripts/detect_video.py'), str(video), '--segments', str(segment_path), '--model', args.model, '--conf', str(args.conf), '--imgsz', str(args.imgsz), '--classes', *map(str, args.classes), '--device', args.device, '--batch-size', str(args.batch_size), '--no-output-video', '--output-csv', str(detections)], check=True, capture_output=True, text=True)
            subprocess.run(base + [str(ROOT / 'scripts/track_norfair.py'), str(video), str(detections), '--segments', str(segment_path), '--distance-threshold', str(args.distance_threshold), '--hit-counter-max', str(args.hit_counter_max), '--no-output-video', '--output-csv', str(tracklets)], check=True, capture_output=True, text=True)
            manifest = dict(expected, outputs={'detections': str(detections), 'tracklets': str(tracklets)})
            manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
            print(f'{video.name}: prepared -> {out}')
            prepared += 1
        except Exception as exc:
            failures += 1
            print(f'{video.name}: FAILED: {exc}')
    print(f'Preparation summary: prepared={prepared} already_prepared={skipped} failed={failures}')
    return 1 if failures else 0

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    mine = sub.add_parser('mine', help='Mine existing CSVs without inference')
    for flag in ('video', 'tracklets'):
        mine.add_argument('--' + flag, type=Path, required=True)
    mine.add_argument('--segments', type=Path, help='LosslessCut CSV; defaults to <video>.csv')
    for flag in ('detections', 'links', 'hands'):
        mine.add_argument('--' + flag, type=Path)
    mine.add_argument('--source-group', help='Recording/session/juggler group for future leakage-safe splits')
    serve = sub.add_parser('serve', help='Local annotation UI; default loopback only')
    serve.add_argument('--host', default='127.0.0.1')
    serve.add_argument('--port', type=int, default=43128)
    export = sub.add_parser('export-yolo', help='Completed full frames only; unassigned, never random frame splits')
    export.add_argument('--output', type=Path, required=True)
    discover = sub.add_parser('discover', help='List videos with matching LosslessCut CSV files')
    discover.add_argument('--source-dir', type=Path, required=True)
    prepare = sub.add_parser('prepare', help='Run segment-aware detector and Norfair preprocessing for a folder')
    prepare.add_argument('--source-dir', type=Path, required=True)
    prepare.add_argument('--output-root', type=Path, default=Path('datasets/juggling_ball_v1/preprocessing'))
    prepare.add_argument('--model', default='yolo26s.pt')
    prepare.add_argument('--conf', type=float, default=0.15)
    prepare.add_argument('--imgsz', type=int, default=960)
    prepare.add_argument('--classes', type=int, nargs='+', default=[32])
    prepare.add_argument('--device', default='auto')
    prepare.add_argument('--batch-size', type=int, default=32)
    prepare.add_argument('--distance-threshold', type=float, default=50)
    prepare.add_argument('--hit-counter-max', type=int, default=15)
    prepare.add_argument('--force', action='store_true')
    for p in (mine, serve, export):
        p.add_argument('--workspace', type=Path, required=True)
    args = parser.parse_args()
    if args.command == 'discover':
        pairs = {video for video, _ in discover_pairs(args.source_dir)}
        for video in discover_video_files(args.source_dir):
            csv_path = Path(str(video) + '.csv')
            if video not in pairs:
                print(json.dumps(dict(video=str(video), error=f'Missing exact matching CSV: {csv_path}')))
                continue
            try:
                segments = parse_losslesscut_csv(csv_path)
                print(json.dumps(dict(video=str(video), segments=str(csv_path), count=len(segments), ranges=[s.as_dict() for s in segments])))
            except ValueError as exc:
                print(json.dumps(dict(video=str(video), segments=str(csv_path), error=str(exc))))
        return 0
    if args.command == 'prepare':
        return prepare_sources(args)
    store = Store(args.workspace)
    if args.command == 'mine':
        for key in ('video', 'tracklets', 'detections', 'links', 'hands'):
            p = getattr(args, key)
            if p and (not p.is_file()):
                parser.error(f'Missing {key}: {p}')
        fps, count, width, height = _video_meta(args.video)
        video_hash = digest(args.video)
        _, segment_path = pair_video_segments(args.video, args.segments)
        segments = parse_losslesscut_csv(segment_path, duration=count / fps)
        segment_hash = digest(segment_path)
        source_key = video_hash + ':' + segment_hash
        source = dict(source_key=source_key, video_path=str(args.video.resolve()), fps=fps, frame_count=count, width=width, height=height, source_group=args.source_group or video_hash, segments=[s.as_dict() for s in segments], inputs={k: dict(path=str(getattr(args, k).resolve()), sha256=digest(getattr(args, k))) for k in ('tracklets', 'detections', 'links', 'hands') if getattr(args, k)})
        source['inputs']['segments'] = dict(path=str(segment_path.resolve()), sha256=segment_hash)
        candidates = mine_candidates(load_tracklets(args.tracklets), load_links(args.links), fps, count, width, height, load_pose(args.hands), segments=segments)
        detections = load_detections(args.detections) if args.detections else {}
        store.mine(source, candidates, detections)
        counts = {name: sum((i['priority'] == p for i in candidates)) for p, name in enumerate(('linked_gap', 'unresolved_boundary', 'ordinary'))}
        reasons = {reason: sum((reason in i['reasons'] for i in candidates)) for reason in ('linked_gap', 'track_end', 'orphan_start', 'ordinary')}
        print(json.dumps(dict(total=len(candidates), exclusive_priority_counts=counts, overlapping_reasons=reasons), indent=2))
    elif args.command == 'serve':
        server = make_server(store, args.host, args.port)
        print(f'Annotation UI: http://{args.host}:{server.server_port}', flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()
    else:
        print(f'Exported {export_yolo(store, args.output)} completed full frames to {args.output}')
    return 0
if __name__ == '__main__':
    raise SystemExit(main())
