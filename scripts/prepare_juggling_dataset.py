#!/usr/bin/env python3
"""Turn an unassigned annotation export into a deterministic segment-level YOLO split."""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.annotation.benchmark import attach_segment_metadata, split_records_by_segment


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--export", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--val-fraction", type=float, default=0.18)
    parser.add_argument("--expected-source", help="Required substring in the sole source filename")
    return parser.parse_args()


def main():
    args = parse_args()
    export = args.export.resolve()
    output = args.output.resolve()
    if output.exists():
        raise ValueError(f"Output already exists: {output}")
    records = attach_segment_metadata([
        json.loads(line) for line in (export / "metadata.jsonl").read_text().splitlines() if line
    ])
    sources = {Path(row["source"]["video_path"]).name for row in records}
    if len(sources) != 1:
        raise ValueError(f"Expected exactly one training source, got {sorted(sources)}")
    source = next(iter(sources))
    if args.expected_source and args.expected_source.lower() not in source.lower():
        raise ValueError(f"Training source {source!r} does not contain {args.expected_source!r}")
    assigned = split_records_by_segment(records, args.val_fraction)
    for split in ("train", "val"):
        (output / "images" / split).mkdir(parents=True)
        (output / "labels" / split).mkdir(parents=True)
    manifest = output / "split_manifest.jsonl"
    with manifest.open("w") as stream:
        for row in assigned:
            split = row["split"]
            item_id = row["id"]
            shutil.copy2(export / row["image"], output / "images" / split / f"{item_id}.jpg")
            shutil.copy2(export / "labels" / "unassigned" / f"{item_id}.txt",
                         output / "labels" / split / f"{item_id}.txt")
            stream.write(json.dumps({
                "id": item_id,
                "source_video": row["source"]["video_path"],
                "frame": row["frame"],
                "timestamp": row["timestamp"],
                "segment": row["segment"],
                "split": split,
                "box_count": len(row["boxes"]),
            }, sort_keys=True) + "\n")
    split_counts = Counter(row["split"] for row in assigned)
    split_boxes = Counter()
    split_segments = {split: set() for split in ("train", "val")}
    for row in assigned:
        split_boxes[row["split"]] += len(row["boxes"])
        split_segments[row["split"]].add(row["segment"]["index"])
    summary = {
        "source": source,
        "total_images": len(assigned),
        "total_boxes": sum(len(row["boxes"]) for row in assigned),
        "zero_box_images": sum(not row["boxes"] for row in assigned),
        "val_fraction_target": args.val_fraction,
        "splits": {
            split: {
                "images": split_counts[split],
                "boxes": split_boxes[split],
                "segments": sorted(split_segments[split]),
            } for split in ("train", "val")
        },
    }
    (output / "split_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    (output / "data.yaml").write_text(
        f"path: {json.dumps(str(output))}\ntrain: images/train\nval: images/val\nnames:\n  0: juggling_ball\n"
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
