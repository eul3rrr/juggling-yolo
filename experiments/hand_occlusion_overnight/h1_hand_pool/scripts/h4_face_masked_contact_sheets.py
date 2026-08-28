#!/usr/bin/env python3
"""Render H4 face-masked contact sheets for visual verification."""
import sys
import json
import shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from h3_contact_sheets import render_sheet  # noqa: E402

H1_DATA = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night/experiments/hand_occlusion_overnight/h1_hand_pool/data")
OUT = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night/experiments/hand_occlusion_overnight/h1_hand_pool/contact_sheets_h4")
OUT.mkdir(exist_ok=True)


def main():
    with (H1_DATA / "h4_face_masked_summary.json").open() as fh:
        data = json.load(fh)
    for r in data["per_link"]:
        if r["n_stationary_clusters"] == 0:
            continue
        l = r["link"]
        link = {
            "stem": l["stem"],
            "from_tid": l["from_tid"],
            "to_tid": l["to_tid"],
            "hand": l["hand"],
            "from_frame": l["from_frame"],
            "to_frame": l["to_frame"],
        }
        out = render_sheet(l["stem"], link, r["stationary_clusters"])
        if out:
            target = OUT / out.name.replace("_h3cluster", "_h4facemask")
            shutil.copy(out, target)
            print(f"  copied to: {target.name}")


if __name__ == "__main__":
    main()
