#!/usr/bin/env python3
"""Filter a detection CSV to detections with confidence >= a threshold.

Reads a minimal-detection CSV written by detect_video.py, filters to
detections whose `confidence` column is >= the given threshold, and
writes the result to a new CSV with the same header and field order.

Used by the yolo26l vs yolo26x confidence-threshold sweep: a single
inference at conf=0.05 is filtered into conf 0.05, 0.075, 0.10 and
0.15 arms without re-running expensive GPU inference.

Usage:
    filter_detections.py INPUT_CSV OUTPUT_CSV --threshold 0.10
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_csv", type=Path)
    parser.add_argument("output_csv", type=Path)
    parser.add_argument("--threshold", type=float, required=True,
                        help="Keep detections with confidence >= threshold.")
    args = parser.parse_args()

    if not 0.0 <= args.threshold <= 1.0:
        raise ValueError("--threshold must be between 0 and 1")

    n_in = 0
    n_out = 0
    fieldnames: list[str] | None = None
    with args.input_csv.open(newline="", encoding="utf-8") as fin, \
         args.output_csv.open("w", newline="", encoding="utf-8") as fout:
        reader = csv.DictReader(fin)
        fieldnames = list(reader.fieldnames or [])
        writer = csv.DictWriter(fout, fieldnames=fieldnames)
        writer.writeheader()
        for row in reader:
            n_in += 1
            if float(row["confidence"]) >= args.threshold:
                writer.writerow(row)
                n_out += 1
    print(f"Filtered {args.input_csv} -> {args.output_csv}: "
          f"{n_in} -> {n_out} (>= {args.threshold})")


if __name__ == "__main__":
    main()