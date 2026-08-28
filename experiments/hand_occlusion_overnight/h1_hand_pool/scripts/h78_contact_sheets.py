"""
H78 contact sheets for the crossed-arm trick (f=890-936) and the
real FOUNTAIN (f=631-669) to visually confirm the wrist-distance
signal difference.
"""

import csv
import json
import os
import subprocess

# Try with PIL
from PIL import Image, ImageDraw, ImageFont

OUT_DIR = "/home/it-admin/projects/juggling-yolo-hand-occlusion-night/experiments/hand_occlusion_overnight/h1_hand_pool/contact_sheets_h78"

PHASES_TO_SHOW = [
    {
        "stem": "identical_balls_trick_000_018",
        "phase": (890, 936),
        "verdict": "OTHER_CROSSED_ARM",
        "n_frames": 6,
    },
    {
        "stem": "identical_balls_trick_000_018",
        "phase": (631, 669),
        "verdict": "FOUNTAIN_REAL",
        "n_frames": 6,
    },
    {
        "stem": "identical_balls_trick_000_018",
        "phase": (977, 1011),
        "verdict": "FOUNTAIN_REAL_WIDE",
        "n_frames": 6,
    },
]

# Pose data and video paths
POSE_FILES = {
    "identical_balls_trick_000_018": "/home/it-admin/projects/juggling-yolo-hand-occlusion-night/detections/identical_balls_trick_000_018_yolo26s-pose.csv",
}

# The original mp4 video path
VIDEO_PATH = "/home/it-admin/.hermes/profiles/juggling-tracker/workspace/juggling-yolo/videos/identical_balls_trick_000_018.mp4"


def extract_frame(video_path, frame, out_path):
    """Extract a single frame using ffmpeg (use select filter, avoid seek issues)."""
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-i", video_path,
        "-vf", f"select=eq(n\\,{frame})",
        "-vsync", "vfr",
        "-q:v", "2",
        out_path,
    ]
    subprocess.run(cmd, check=True)


def load_pose(pose_path):
    poses = {}
    with open(pose_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            frame = int(row["frame"])
            lx = float(row["left_wrist_x"]) if row["left_wrist_x"] else None
            ly = float(row["left_wrist_y"]) if row["left_wrist_y"] else None
            rx = float(row["right_wrist_x"]) if row["right_wrist_x"] else None
            ry = float(row["right_wrist_y"]) if row["right_wrist_y"] else None
            poses[frame] = (lx, ly, rx, ry)
    return poses


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    for phase_info in PHASES_TO_SHOW:
        stem = phase_info["stem"]
        start, end = phase_info["phase"]
        verdict = phase_info["verdict"]
        n_show = phase_info["n_frames"]
        frames = [start + (end - start) * i // (n_show - 1) for i in range(n_show)]

        pose = load_pose(POSE_FILES[stem])

        # Extract frames
        frame_imgs = []
        for f in frames:
            tmp = f"/tmp/h78_frame_{f}.jpg"
            extract_frame(VIDEO_PATH, f, tmp)
            frame_imgs.append((f, tmp))

        # Compose contact sheet: 2 cols x 3 rows
        cols = 2
        rows = (n_show + cols - 1) // cols
        first_img = Image.open(frame_imgs[0][1])
        w, h = first_img.size
        scale = 0.4
        sw, sh = int(w * scale), int(h * scale)
        # Account for label
        label_h = 30
        sheet_w = sw * cols
        sheet_h = (sh + label_h) * rows
        sheet = Image.new("RGB", (sheet_w, sheet_h), "white")
        draw = ImageDraw.Draw(sheet)
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 14)
        except Exception:
            font = ImageFont.load_default()

        for i, (f, tmp) in enumerate(frame_imgs):
            r = i // cols
            c = i % cols
            x = c * sw
            y = r * (sh + label_h)
            img = Image.open(tmp).resize((sw, sh))
            sheet.paste(img, (x, y + label_h))
            # Label
            p = pose.get(f)
            if p:
                lx, ly, rx, ry = p
                if None not in (lx, ly, rx, ry):
                    import math
                    d = math.sqrt((lx - rx) ** 2 + (ly - ry) ** 2)
                    label = f"f={f} wrist_dist={d:.1f}"
                else:
                    label = f"f={f} (no pose)"
            else:
                label = f"f={f} (no pose)"
            draw.text((x + 5, y + 5), label, fill="black", font=font)

        out_path = f"{OUT_DIR}/phase_{stem}_f{start}-{end}_{verdict}.png"
        sheet.save(out_path)
        print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
