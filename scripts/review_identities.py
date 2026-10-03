#!/usr/bin/env python3
"""Local website to review scripts/track_identities.py output.

Shows the rendered review video next to a per-ball state timeline and the list of
links (hidden first, then costliest), lets you jump to each link and mark it
correct / wrong / unclear with a note. Labels are written to a CSV as they are made.
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import socket
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.tracking.review_server import LabelStore, make_server  # noqa: E402


def tailscale_ipv4() -> str | None:
    binary = shutil.which("tailscale")
    if not binary:
        return None
    try:
        out = subprocess.check_output([binary, "ip", "-4"], timeout=2.0, text=True)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None
    for line in out.splitlines():
        if re.match(r"^100\.\d+\.\d+\.\d+$", line.strip()):
            return line.strip()
    return None


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--identity-dir", type=Path, required=True, help="output dir of track_identities.py")
    p.add_argument("--video", type=Path, default=None,
                   help="rendered review video (default: <identity-dir>/review.mp4)")
    p.add_argument("--labels", type=Path, default=None,
                   help="labels CSV (default: <identity-dir>/review_labels.csv)")
    p.add_argument("--name", default=None, help="title shown in the page")
    p.add_argument("--bind", default=None, help="host to bind (default: Tailscale IP, else localhost)")
    p.add_argument("--start-port", type=int, default=43140)
    p.add_argument("--port-attempts", type=int, default=20)
    return p.parse_args()


def main() -> int:
    args = parse_args()
    video = args.video or args.identity_dir / "review.mp4"
    if not video.is_file():
        print(f"No review video at {video}. Render it first:\n"
              f"  .venv/bin/python scripts/render_ball_states.py --video <source.mp4> "
              f"--identity-dir {args.identity_dir} --tracklets <tracklets.csv>")
        return 1
    for name in ("ball_states.csv", "links.csv", "summary.json"):
        if not (args.identity_dir / name).is_file():
            print(f"Missing {args.identity_dir / name}; run track_identities.py first.")
            return 1
    labels = LabelStore(args.labels or args.identity_dir / "review_labels.csv")
    tailscale = tailscale_ipv4()
    host = args.bind or tailscale or "127.0.0.1"
    server = None
    for port in range(args.start_port, args.start_port + args.port_attempts):
        try:
            server = make_server(args.identity_dir, video, labels, host, port, args.name or args.identity_dir.name)
            break
        except OSError:
            continue
    if server is None:
        print("No free port found")
        return 1
    port = server.server_address[1]
    print(f"Identity review running on http://{host}:{port}")
    if host == "127.0.0.1":
        print("No Tailscale detected; bound to localhost. From your laptop:")
        print(f"  ssh -N -L {port}:127.0.0.1:{port} {os.environ.get('USER', 'user')}@{socket.gethostname()}")
        print(f"then open http://127.0.0.1:{port}")
    print(f"Labels: {labels.path}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
