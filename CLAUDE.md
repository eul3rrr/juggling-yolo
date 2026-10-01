# juggling-yolo

Ball detection, tracking and identity repair for juggling videos (Ultralytics YOLO26, Norfair, OpenCV, FastAPI live UI). `README.md` documents every pipeline stage and its command.

## Working here

- Python lives in `.venv/` (CUDA PyTorch). Run things as `.venv/bin/python scripts/<name>.py`; tests with `.venv/bin/python -m pytest tests`.
- `.gitignore` is an allowlist: everything is ignored unless a `!` line names it. A new file will not show in `git status` until you add an exception for it.
- `datasets/` is ignored here and is its own git repo, backed up to the private `juggling-data` repo. Commit and push there after annotation or training work.
- Source videos are in `~/Downloads/juggling_videos`.
- This repo is public. Do not commit personal data or credentials.

## Layout

- Main clone: this folder, branch `feature/juggling-ball-annotation-v1` (the newest work; `main` is behind).
- Worktrees: `../juggling-yolo-detector-seg-comparison`, `../juggling-yolo-hand-occlusion-night`. They share this clone's `.git` and `.venv`.
- No branch has been merged into `main` yet.

## Known loose ends

- `src/vision_stitch/judge.py` looks up an OpenRouter key in the Hermes `juggling-tracker` profile, which has been archived to `~/.hermes/archive/`.
