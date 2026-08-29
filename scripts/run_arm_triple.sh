#!/usr/bin/env bash
# Run the three perception arms on a single video in sequence.
# Usage: run_arm_triple.sh <video_path>
#
# Outputs (all under the project root):
#   outputs/<video>_<model>_classes-32.mp4          detection overlay
#   outputs/detector_seg_comparison/<video>_<model>_classes-32_overlay.mp4  seg overlay
#   detections/<video>_<model>_classes-32.csv       minimal detection CSV
#   detections/<video>_<model>_classes-32_instances.csv  instance + mask CSV (seg only)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
VIDEO="$1"
STEM="$(basename "$VIDEO" .mp4)"
CONF=0.15
IMGSZ=960
DEVICE="${DEVICE:-auto}"

echo "=== ARM A: yolo26s ==="
./.venv/bin/python scripts/detect_video.py "$VIDEO" \
    --model yolo26s.pt --conf "$CONF" --imgsz "$IMGSZ" \
    --classes 32 --device "$DEVICE" \
    --output-dir outputs/detector_seg_comparison/ \
    --detections-dir detections/detector_seg_comparison/

echo "=== ARM B: yolo26l ==="
./.venv/bin/python scripts/detect_video.py "$VIDEO" \
    --model yolo26l.pt --conf "$CONF" --imgsz "$IMGSZ" \
    --classes 32 --device "$DEVICE" \
    --output-dir outputs/detector_seg_comparison/ \
    --detections-dir detections/detector_seg_comparison/

echo "=== ARM C: yolo26l-seg ==="
./.venv/bin/python scripts/segment_video.py "$VIDEO" \
    --model yolo26l-seg.pt --conf "$CONF" --imgsz "$IMGSZ" \
    --classes 32 --device "$DEVICE" \
    --output-dir outputs/detector_seg_comparison/ \
    --detections-dir detections/detector_seg_comparison/

echo "DONE triple for $STEM"
