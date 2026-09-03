#!/usr/bin/env python3
"""Run the local Juggling Tracker Live V1 UI."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.live.session import create_app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--video", type=Path, default=None, help="optional initial prerecorded video")
    parser.add_argument("--model", default="yolo26m.pt", help="local YOLO checkpoint")
    parser.add_argument("--device", default="auto", help="auto, cpu, 0, or another Ultralytics device")
    args = parser.parse_args()
    import uvicorn
    app = create_app()
    print(f"Juggling Tracker Live: http://{args.host}:{args.port}")
    if args.video:
        app.state.config = {"source": "video", "video_path": str(args.video.resolve()), "model": args.model, "device": args.device}
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
