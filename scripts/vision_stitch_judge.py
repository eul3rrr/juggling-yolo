#!/usr/bin/env python3
"""Vision-LLM tracklet stitching judge: evidence, judging, and human review.

    prepare  build END -> candidate events and the exact images the model will see
    judge    ask a vision model for one stitch decision per event (resumable)
    serve    local review UI: model verdict, evidence, and human labels
    summary  agreement statistics and a markdown report

Read-only with respect to the tracking pipeline: it consumes existing tracklet
CSVs and video frames and never changes the stitcher or any identity layer.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.vision_stitch.candidates import build_events, load_inputs  # noqa: E402
from src.annotation.segments import segment_frame_bounds  # noqa: E402
from src.vision_stitch.evidence import (EvidenceConfig, FrameReader,  # noqa: E402
                                       build_event_evidence, manifest_is_current)
from src.vision_stitch.judge import (DEFAULT_MODEL, JudgeClient, JudgeConfig,  # noqa: E402
                                     event_slug, load_manifests, resolve_api_key, run_judge)
from src.vision_stitch.prompt import PROMPT_VERSION  # noqa: E402
from src.vision_stitch.server import LabelStore, make_server  # noqa: E402


def digest(path: Path) -> str:
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def command_prepare(args: argparse.Namespace) -> int:
    video = args.video.resolve()
    reader = FrameReader(video)
    try:
        tracks, segments = load_inputs(video, args.tracklets, args.segments, reader.frame_count, reader.fps)
        events, stats = build_events(tracks, segments, reader.fps, reader.frame_count,
                                     window_frames=args.window, top_k=args.top_k)
        # An END on a segment cut is an artefact of the LosslessCut range, not a lost
        # ball; the mining layer uses the same 0.2 s margin.
        if args.edge_margin > 0:
            margin = max(1, round(args.edge_margin * reader.fps))
            kept = []
            for event in events:
                segment = segments[event["segment_index"]]
                start, end = segment_frame_bounds(segment, reader.fps, reader.frame_count)
                if min(abs(event["source"]["last_frame"] - start),
                       abs(event["source"]["last_frame"] - end)) <= margin:
                    continue
                kept.append(event)
            stats["excluded_segment_edge"] = len(events) - len(kept)
            events = kept
        if args.only:
            wanted = set(args.only)
            events = [e for e in events if e["event_key"] in wanted or event_slug(e["event_key"]) in wanted]
            stats["filtered_to"] = len(events)
        if args.limit is not None:
            events = events[:args.limit]
        out_root = args.out_root.resolve()
        events_root = out_root / "events"
        events_root.mkdir(parents=True, exist_ok=True)
        config = EvidenceConfig()
        built = skipped = 0
        for event in events:
            out_dir = events_root / event_slug(event["event_key"])
            manifest_path = out_dir / "manifest.json"
            if manifest_path.is_file() and not args.force:
                try:
                    existing = json.loads(manifest_path.read_text())
                except ValueError:
                    existing = {}
                if manifest_is_current(existing, event, config, PROMPT_VERSION, out_dir):
                    skipped += 1
                    continue
            build_event_evidence(event, tracks, reader, out_dir, config, PROMPT_VERSION)
            built += 1
        (out_root / "events.json").write_text(json.dumps(events, indent=2, sort_keys=True) + "\n")
        run_manifest = dict(
            created_at=datetime.now(timezone.utc).isoformat(),
            git_commit=git_commit(),
            video=str(video), video_sha256=digest(video),
            tracklets=str(args.tracklets.resolve()), tracklets_sha256=digest(args.tracklets),
            segments=str((Path(args.segments) if args.segments else Path(str(video) + ".csv")).resolve()),
            fps=reader.fps, frame_count=reader.frame_count,
            width=reader.width, height=reader.height,
            window_frames=args.window, top_k=args.top_k,
            prompt_version=PROMPT_VERSION, evidence_config=config.as_dict(),
            event_count=len(events), evidence_built=built, evidence_reused=skipped, stats=stats,
        )
        (out_root / "run_manifest.json").write_text(json.dumps(run_manifest, indent=2, sort_keys=True) + "\n")
        print(json.dumps(dict(events=len(events), evidence_built=built, evidence_reused=skipped,
                              events_root=str(events_root), stats=stats), indent=2, sort_keys=True))
    finally:
        reader.release()
    return 0


def command_judge(args: argparse.Namespace) -> int:
    config = JudgeConfig(model=args.model, max_tokens=args.max_tokens,
                         reasoning_effort=args.reasoning_effort, timeout=args.timeout)
    client = JudgeClient(config, resolve_api_key(args.api_key))
    stats = run_judge(args.events_root, args.results_root, client, config,
                      concurrency=args.concurrency, limit=args.limit, only=args.only, force=args.force)
    print(json.dumps(dict(model=config.model, **stats), indent=2, sort_keys=True))
    return 0


def command_serve(args: argparse.Namespace) -> int:
    labels = LabelStore(args.labels)
    server = make_server(args.events_root, args.results_root, labels, args.video,
                         host=args.host, port=args.port)
    print(f"Vision-stitch review UI: http://{args.host}:{server.server_port}", flush=True)
    print(f"Labels: {labels.path}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


def normalized_track_id(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def summarize(events_root: Path, results_root: Path, labels: LabelStore) -> dict:
    manifests = {m["event_key"]: m for m in load_manifests(events_root)}
    rows = []
    for slug in sorted({event_slug(key) for key in manifests}):
        result_path = Path(results_root) / f"{slug}.json"
        if not result_path.is_file():
            continue
        result = json.loads(result_path.read_text())
        verdict = result.get("verdict", {}) or {}
        manifest = manifests.get(result.get("event_key"), {})
        label = labels.get(result.get("event_key")) or {}
        chosen = verdict.get("candidate_letter")
        model_track = normalized_track_id(result.get("candidate_track_id"))
        cv_track = (manifest.get("cv_rank1") or {}).get("track_id")
        rows.append(dict(
            event_key=result.get("event_key"), decision=verdict.get("decision"),
            candidate_letter=chosen, model_track=model_track,
            confidence=verdict.get("confidence"), parse_ok=verdict.get("parse_ok"),
            cv_track=cv_track, cv_error=(manifest.get("cv_rank1") or {}).get("prediction_error"),
            labelled=label.get("label") or "",
            agrees_with_cv=(bool(model_track) and model_track == cv_track) if verdict.get("decision") == "stitch" else None,
        ))
    labelled = [r for r in rows if r["labelled"]]
    stitched = [r for r in rows if r["decision"] == "stitch"]
    summary = dict(
        events=len(rows),
        labelled=len(labelled),
        model_stitch=len(stitched),
        model_none=sum(1 for r in rows if r["decision"] == "none"),
        model_uncertain=sum(1 for r in rows if r["decision"] == "uncertain"),
        parse_failures=sum(1 for r in rows if not r["parse_ok"]),
        vision_matches_cv=sum(1 for r in stitched if r["agrees_with_cv"]),
        vision_differs_from_cv=sum(1 for r in stitched if r["agrees_with_cv"] is False),
        human_label_counts={value: sum(1 for r in labelled if r["labelled"] == value)
                            for value in ("correct", "wrong", "unclear")},
        vision_vs_human=dict(
            stitch_correct=sum(1 for r in labelled if r["decision"] == "stitch" and r["labelled"] == "correct"),
            stitch_wrong=sum(1 for r in labelled if r["decision"] == "stitch" and r["labelled"] == "wrong"),
            none_correct=sum(1 for r in labelled if r["decision"] == "none" and r["labelled"] == "correct"),
            none_wrong=sum(1 for r in labelled if r["decision"] == "none" and r["labelled"] == "wrong"),
        ),
        mean_confidence=round(sum(r["confidence"] or 0 for r in rows) / len(rows), 4) if rows else None,
        total_cost_usd=round(sum(json.loads(p.read_text()).get("usage", {}).get("cost_usd") or 0
                                for p in Path(results_root).glob("*.json")), 4),
    )
    return dict(summary=summary, rows=rows)


def command_summary(args: argparse.Namespace) -> int:
    labels = LabelStore(args.labels)
    result = summarize(args.events_root, args.results_root, labels)
    print(json.dumps(result["summary"], indent=2, sort_keys=True))
    if args.output:
        lines = ["# Vision-stitch judge — summary", "",
                 f"Generated: {datetime.now(timezone.utc).isoformat()}", "",
                 "| metric | value |", "| --- | --- |"]
        for key, value in result["summary"].items():
            lines.append(f"| `{key}` | {json.dumps(value)} |")
        lines += ["", "## Per event", "", "| event | model | conf | CV rank-1 | CV err px | human label |",
                  "| --- | --- | --- | --- | --- | --- |"]
        for row in result["rows"]:
            lines.append(f"| `{row['event_key']}` | {row['decision']}"
                         f"{' → ' + row['candidate_letter'] if row['candidate_letter'] else ''}"
                         f" | {'' if row['confidence'] is None else round(row['confidence'], 2)}"
                         f" | {row['cv_track']} | {'' if row['cv_error'] is None else round(row['cv_error'])}"
                         f" | {row['labelled'] or '—'} |")
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text("\n".join(lines) + "\n")
        print(f"wrote {args.output}")
    return 0


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    sub = root.add_subparsers(dest="command", required=True)

    prepare = sub.add_parser("prepare", help="build candidate events + model evidence images")
    prepare.add_argument("--video", type=Path, required=True)
    prepare.add_argument("--tracklets", type=Path, required=True)
    prepare.add_argument("--segments", type=Path, help="LosslessCut CSV; defaults to <video>.csv")
    prepare.add_argument("--out-root", type=Path, required=True)
    prepare.add_argument("--window", type=int, default=30, help="candidate window in frames after the END")
    prepare.add_argument("--top-k", type=int, default=3, help="candidates given to the model per END")
    prepare.add_argument("--edge-margin", type=float, default=0.2,
                         help="seconds; drop ENDs this close to a LosslessCut segment edge (0 disables)")
    prepare.add_argument("--limit", type=int)
    prepare.add_argument("--only", nargs="*", help="event keys or slugs to include")
    prepare.add_argument("--force", action="store_true")

    judge = sub.add_parser("judge", help="ask the vision model for stitch decisions")
    judge.add_argument("--events-root", type=Path, required=True)
    judge.add_argument("--results-root", type=Path, required=True)
    judge.add_argument("--model", default=DEFAULT_MODEL)
    judge.add_argument("--api-key", help="OpenRouter key; defaults to env/profile store")
    judge.add_argument("--concurrency", type=int, default=6)
    judge.add_argument("--limit", type=int)
    judge.add_argument("--only", nargs="*")
    judge.add_argument("--max-tokens", type=int, default=16000)
    judge.add_argument("--reasoning-effort", default="low", choices=["low", "medium", "high", "none"])
    judge.add_argument("--timeout", type=int, default=900)
    judge.add_argument("--force", action="store_true")

    serve = sub.add_parser("serve", help="local review UI")
    serve.add_argument("--events-root", type=Path, required=True)
    serve.add_argument("--results-root", type=Path, required=True)
    serve.add_argument("--video", type=Path, required=True)
    serve.add_argument("--labels", type=Path, required=True)
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=43130)

    summary = sub.add_parser("summary", help="agreement statistics + markdown report")
    summary.add_argument("--events-root", type=Path, required=True)
    summary.add_argument("--results-root", type=Path, required=True)
    summary.add_argument("--labels", type=Path, required=True)
    summary.add_argument("--output", type=Path)

    return root


def main() -> int:
    args = parser().parse_args()
    if args.command == "prepare":
        return command_prepare(args)
    if args.command == "judge":
        return command_judge(args)
    if args.command == "serve":
        return command_serve(args)
    return command_summary(args)


if __name__ == "__main__":
    raise SystemExit(main())
