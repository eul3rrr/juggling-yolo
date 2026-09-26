"""Prompt assembly for the vision stitch judge.

The same manifest that drives the review UI drives the prompt, so the human can
see exactly which frames (and which timestamps) were given to the model.
"""
from __future__ import annotations

import base64
from pathlib import Path

PROMPT_VERSION = "v1"

INSTRUCTIONS = """You are a stitching judge for a juggling-ball tracker on a {fps:.2f} fps {width}x{height} video.
A tracker lost one ball: tracklet {source_id} ENDS. Later tracklets started nearby; they are candidates {letters}.

You are shown ball-centred crops (a ring marks the ball) and one full frame at the moment of loss.
Every image carries its timestamp in seconds and its frame number, and the same values are repeated in the text
lines below each image, so you can reason about timing and speed.

Physical rule for juggling: while a ball is held in a hand it usually produces no detections; when it is thrown
again a new tracklet appears. So a hand-mediated handoff to a later tracklet is still the SAME physical ball.
A different ball passing through the same area is NOT the same ball.

Decide whether the END tracklet continues as one of the candidates, or as none of them.
Use: does the END motion extrapolate into the candidate start (direction and speed)? Do timing and hand positions
make a catch-and-throw plausible? Is the ball still visible but simply missed by the detector? If two balls are
visible at the same moment, they are distinct objects.

Answer with STRICT JSON only, no prose and no code fences:
{{"decision":"stitch"|"none"|"uncertain","candidate":"A"|"B"|...|null,"confidence":0.0-1.0,"reason":"<=30 words"}}"""


def _data_url(path: Path, quality_note: str = "image/jpeg") -> str:
    encoded = base64.b64encode(path.read_bytes()).decode()
    return f"data:{quality_note};base64,{encoded}"


def describe_image(image: dict, manifest: dict) -> str:
    """One text line per image: role, seconds, frame number, and what it shows."""
    role = image["role"]
    seconds, frame = image["seconds"], image["frame"]
    offset = image.get("requested_offset_frames")
    delta = "" if offset is None else f" ({offset / manifest['video']['fps']:+.2f}s from the reference frame)"
    if role == "source_pre":
        what = f"END tracklet T{image['track_id']}, still being detected before the loss"
    elif role == "source_lost":
        what = f"last position of END tracklet T{image['track_id']} after the detection stops"
    elif role == "candidate":
        what = f"candidate {image['letter']} = tracklet T{image['track_id']}, just after it starts"
    else:
        what = "full frame at the moment of loss; END and candidate starts are ringed, trails show observed motion"
    return f"{image['role']} {image['role_index']}: t={seconds:.2f}s (frame {frame}){delta} — {what}"


def build_request(manifest: dict, images_dir: Path) -> list[dict]:
    """Build the OpenRouter chat content list for one event."""
    video = manifest["video"]
    letters = [c["letter"] for c in manifest["candidates"]]
    header = INSTRUCTIONS.format(fps=video["fps"], width=video["width"], height=video["height"],
                                 source_id=manifest["source"]["track_id"],
                                 letters=", ".join(letters) if letters else "(none)")
    lines = [header, "",
             f"END tracklet T{manifest['source']['track_id']} last detection: t={manifest['source']['last_seconds']:.2f}s "
             f"(frame {manifest['source']['last_frame']}), observed length {manifest['source']['observed_len']} frames.",
             "Candidates, ranked by constant-velocity prediction error (closest first):"]
    for candidate in manifest["candidates"]:
        lines.append(
            f"  {candidate['letter']} = tracklet T{candidate['track_id']} — starts t={candidate['first_frame'] / video['fps']:.2f}s "
            f"(frame {candidate['first_frame']}), {candidate['gap_frames']} frames ({candidate['gap_seconds']:.2f}s) after the loss, "
            f"straight-line prediction error {candidate['prediction_error']:.0f} px, observed length {candidate['observed_len']} frames.")
    lines += ["", "Images follow in order, each preceded by its own description:", ""]

    content: list[dict] = [{"type": "text", "text": "\n".join(lines)}]
    for image in manifest["images"]:
        content.append({"type": "text", "text": describe_image(image, manifest)})
        content.append({"type": "image_url",
                        "image_url": {"url": _data_url(Path(images_dir) / image["file"])}})
    content.append({"type": "text", "text": "Decide now. STRICT JSON only."})
    return content
