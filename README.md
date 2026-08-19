# Juggling YOLO Detection Experiment

This isolated experiment evaluates a pretrained Ultralytics YOLO26 COCO detection
model on juggling videos. It performs frame-local object detection only: no
training, fine-tuning, tracking, segmentation, pose estimation, HSV filtering, or
persistent ball identities.

## Layout

- `videos/`: short input videos
- `outputs/`: annotated videos with boxes, class names, and confidence scores
- `detections/`: one pixel-coordinate CSV per run
- `scripts/detect_video.py`: streaming Python inference script
- `.venv/`: isolated Python environment

## Environment

The environment was created with Python 3.14 and CUDA-enabled PyTorch for the
machine's NVIDIA GPU. Recreate it with:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip setuptools wheel
.venv/bin/python -m pip install torch torchvision \
  --index-url https://download.pytorch.org/whl/cu130
.venv/bin/python -m pip install ultralytics==8.4.123
```

## Run unfiltered COCO detection

This reveals which COCO classes YOLO assigns to juggling balls and other objects:

```bash
.venv/bin/python scripts/detect_video.py \
  videos/identical_balls_trick_000_018.mp4 \
  --model yolo26s.pt --conf 0.15 --imgsz 960 --device auto
```

The executable script also finds and uses the project's `.venv` automatically,
so from the `scripts/` directory the equivalent form is:

```bash
./detect_video.py ../videos/identical_balls_trick_000_018.mp4 \
  --model yolo26s.pt --conf 0.15 --imgsz 960 --device auto
```

## Run sports-ball detection

COCO class 32 is `sports ball`:

```bash
.venv/bin/python scripts/detect_video.py \
  videos/identical_balls_trick_000_018.mp4 \
  --model yolo26s.pt --conf 0.15 --imgsz 960 \
  --classes 32 --device auto
```

`--device auto` selects GPU 0 when CUDA is available and otherwise uses CPU.
Every frame is processed with `vid_stride=1`, and Ultralytics results are consumed
with `stream=True` to avoid retaining the complete video in memory.

CSV columns are: `video`, `frame`, `time_seconds`, `class_id`, `class_name`,
`confidence`, `x1`, `y1`, `x2`, `y2`, `center_x`, `center_y`, `width`, and
`height`. Bounding-box values are pixel coordinates in the original video.
