#!/usr/bin/env python3
"""Reproducible full-network Ultralytics detector fine-tuning wrapper."""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def digest(path: Path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--experiment", type=Path, required=True)
    parser.add_argument("--imgsz", type=int, default=960)
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--patience", type=int, default=12)
    parser.add_argument("--batch", type=float, default=-1, help="-1 requests Ultralytics auto-batch")
    parser.add_argument("--device", default="0")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--seed", type=int, default=1337)
    return parser.parse_args()


def main():
    import cv2
    import torch
    import ultralytics
    from ultralytics import YOLO

    args = parse_args()
    model = args.model.resolve()
    data = args.data.resolve()
    experiment = args.experiment.resolve()
    run_dir = experiment / "training"
    if run_dir.exists():
        raise ValueError(f"Training output already exists: {run_dir}")
    experiment.mkdir(parents=True, exist_ok=True)
    config = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "model": str(model),
        "model_sha256": digest(model),
        "data": str(data),
        "imgsz": args.imgsz,
        "epochs": args.epochs,
        "patience": args.patience,
        "batch": args.batch,
        "device": args.device,
        "workers": args.workers,
        "seed": args.seed,
        "full_network": True,
        "freeze": None,
        "versions": {
            "python": platform.python_version(),
            "torch": torch.__version__,
            "cuda": torch.version.cuda,
            "ultralytics": ultralytics.__version__,
            "opencv": cv2.__version__,
        },
    }
    (experiment / "training_config.json").write_text(json.dumps(config, indent=2, sort_keys=True) + "\n")
    result = YOLO(str(model)).train(
        data=str(data), task="detect", imgsz=args.imgsz, epochs=args.epochs,
        patience=args.patience, batch=args.batch, device=args.device,
        workers=args.workers, seed=args.seed, deterministic=True,
        project=str(experiment), name="training", exist_ok=False,
        pretrained=True, verbose=True,
    )
    metrics = {key: float(value) for key, value in getattr(result, "results_dict", {}).items()}
    (experiment / "training_result.json").write_text(json.dumps({
        "metrics": metrics,
        "best": str((run_dir / "weights" / "best.pt").resolve()),
        "last": str((run_dir / "weights" / "last.pt").resolve()),
    }, indent=2, sort_keys=True) + "\n")
    print(json.dumps(metrics, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
