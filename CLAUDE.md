# juggling-yolo

Ball detection, tracking and identity repair for juggling videos (Ultralytics YOLO26, Norfair, OpenCV, FastAPI live UI). `README.md` is the public front page with the frozen demo; `docs/REFERENCE.md` documents every pipeline stage and its command; `ROADMAP.md` holds next steps, ideas to try and dropped experiments.

## Working here

- Python lives in `.venv/` (CUDA PyTorch). Run things as `.venv/bin/python scripts/<name>.py`; tests with `.venv/bin/python -m pytest tests`.
- The detector weights `yolo26l.pt` sit in the repo root and are not tracked (`*.pt` is ignored).
- `.gitignore` is a normal ignore file: new files show up in `git status`. Videos, weights, `outputs/` and `datasets/` are ignored.
- `datasets/` is its own git repo, backed up to the private `juggling-data` repo. Commit and push there after annotation or training work.
- Source videos are in `~/Downloads/juggling_videos` and `videos/`.
- This repo is public. Do not commit personal data or credentials; videos of the user stay in `videos/`, which is ignored.
- `tests/test_demo_snapshot.py` pins the frozen demo: if a hand script changes, `docs/demo-manifest.json` must be refreshed, and it checks every relative link in the docs.

## Branches

- `main` is the current working version. Start each piece of work on its own branch from `main` (`feature/...`, `fix/...`, `experiment/...`), merge it back when it works, then delete the branch.
- When an experiment ends, record the conclusion in `ROADMAP.md` ("Tried and dropped") before deleting its branch.
- Code removed from the tree but worth finding again is tagged `archive/<name>` at the last commit that had it.
- Backups of deleted branches and local leftovers are in `~/backups/juggling-yolo/`.
