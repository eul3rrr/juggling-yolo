# Setup

Python 3.14 was used for the current environment. Create a virtual environment and install a PyTorch build appropriate for your machine. For the CUDA 13.0 setup used during development:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip setuptools wheel
.venv/bin/python -m pip install torch torchvision \
  --index-url https://download.pytorch.org/whl/cu130
.venv/bin/python -m pip install -r requirements.txt
```

CPU-only and other CUDA installations should use the matching command from the [PyTorch installation guide](https://pytorch.org/get-started/locally/) before installing `requirements.txt`.

Place input clips in `videos/`. The examples below use:

- `videos/identical_balls_trick_000_018.mp4`
- `videos/youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090.mp4`


## Tests

```bash
.venv/bin/python -m pytest -q
```

Run all commands from the repository root. The GIF-only workflow also requires `ffmpeg`; video metadata checks use `ffprobe`. Full demo rendering needs the original source clip, which is not distributed here.

See [the README](../README.md) for the frozen demo and [baseline commands](BASELINES.md) for earlier tracker experiments.
