#!/usr/bin/env python3
"""H39 - record visual QA verdicts for FOUNTAIN_3+ phase contact sheets.

The vision_analyze results are manually recorded here as a structured
verdict file. This is the source of truth for H39's visual precision
analysis.
"""
import csv
import json
from pathlib import Path

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DATA = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool" / "data"

# Visual QA verdicts from vision_analyze runs (2026-08-28 14:00-14:30)
# Each entry: phase, video, vision_verdict, hand_occ_evidence, h39v1_decision
VERDICTS = [
    # identical FOUNTAIN_3+ phases (n>=10)
    {"video": "identical", "phase": "f243-252", "n": 10, "hand_occ_h36": 1,
     "vision_verdict": "FOUNTAIN", "hand_occ_vision": "left+right (both occupied in all frames)",
     "h39v1_decision": "KEPT", "h39v2_decision": "KEPT",
     "comment": "Real FOUNTAIN — right-handed, hands both visible occupied"},
    {"video": "identical", "phase": "f263-312", "n": 50, "hand_occ_h36": 0,
     "vision_verdict": "MIXED", "hand_occ_vision": "left hand occupied in most frames",
     "h39v1_decision": "REJECTED", "h39v2_decision": "KEPT",
     "comment": "Real juggling with hand-occupancy that H36 chain events miss"},
    {"video": "identical", "phase": "f411-449", "n": 39, "hand_occ_h36": 0,
     "vision_verdict": "MIXED", "hand_occ_vision": "left hand occupied in 4/6 frames",
     "h39v1_decision": "REJECTED", "h39v2_decision": "REJECTED",
     "comment": "Real juggling with hand-occupancy (left dominant)"},
    {"video": "identical", "phase": "f631-669", "n": 39, "hand_occ_h36": 0,
     "vision_verdict": "FOUNTAIN", "hand_occ_vision": "left hand occupied in all frames",
     "h39v1_decision": "REJECTED", "h39v2_decision": "KEPT",
     "comment": "Real left-hand FOUNTAIN — hand-occupancy visible"},
    {"video": "identical", "phase": "f685-716", "n": 32, "hand_occ_h36": 0,
     "vision_verdict": "FOUNTAIN", "hand_occ_vision": "left+right (both occupied, right=high, left=low)",
     "h39v1_decision": "REJECTED", "h39v2_decision": "KEPT",
     "comment": "Real right-handed FOUNTAIN — both hands visible, hands both occupied in all frames"},
    {"video": "identical", "phase": "f733-766", "n": 34, "hand_occ_h36": 1,
     "vision_verdict": "QA_PENDING", "hand_occ_vision": "QA pending",
     "h39v1_decision": "REJECTED", "h39v2_decision": "KEPT",
     "comment": "Vision QA not completed (vision_analyze error); H36 has CATCH event at boundary"},
    {"video": "identical", "phase": "f860-871", "n": 12, "hand_occ_h36": 0,
     "vision_verdict": "MIXED", "hand_occ_vision": "left+right (crossed-arms juggling, both occupied)",
     "h39v1_decision": "REJECTED", "h39v2_decision": "KEPT",
     "comment": "Real crossed-arms juggling (MIXED/Mill's-Mess-like), not FOUNTAIN"},
    {"video": "identical", "phase": "f977-1011", "n": 35, "hand_occ_h36": 0,
     "vision_verdict": "OTHER (hold trick)", "hand_occ_vision": "left+right (both occupied, statue/columns pattern)",
     "h39v1_decision": "REJECTED", "h39v2_decision": "REJECTED",
     "comment": "Real hold/columns trick — both hands occupied throughout, not a flowing FOUNTAIN"},
    {"video": "identical", "phase": "f1029-1050", "n": 22, "hand_occ_h36": 1,
     "vision_verdict": "OTHER (2-ball exercise)", "hand_occ_vision": "right hand occupied, only 2 balls visible",
     "h39v1_decision": "REJECTED", "h39v2_decision": "KEPT",
     "comment": "2-ball exercise (n=2), not 3-ball FOUNTAIN. H12 v8 misclassification."},
    # YouTube FOUNTAIN_3+ phases (n>=10)
    {"video": "youtube", "phase": "f339-374", "n": 36, "hand_occ_h36": 0,
     "vision_verdict": "CASCADE", "hand_occ_vision": "right hand occupied in 4/6 frames",
     "h39v1_decision": "REJECTED", "h39v2_decision": "KEPT",
     "comment": "Real 5-ball CASCADE — H12 v8 misclassification"},
    {"video": "youtube", "phase": "f800-861", "n": 62, "hand_occ_h36": 16,
     "vision_verdict": "MIXED", "hand_occ_vision": "left+right (both occupied, asymmetric)",
     "h39v1_decision": "PARTIAL REJECT", "h39v2_decision": "KEPT",
     "comment": "Real juggling with hand-occupancy — H12 v8 over-counts FOUNTAIN"},
]


def main():
    out = H1_DATA / "h39_visual_qa_verdicts.csv"
    with out.open("w", newline="") as f:
        fieldnames = list(VERDICTS[0].keys())
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(VERDICTS)
    print(f"Saved: {out}")

    # Compute precision summary
    identical = [v for v in VERDICTS if v["video"] == "identical"]
    youtube = [v for v in VERDICTS if v["video"] == "youtube"]
    n_qa = sum(1 for v in VERDICTS if v["vision_verdict"] != "QA_PENDING")

    # H12 v8 correctly classified (vision matches): real FOUNTAIN_3+
    correct_h12v8 = sum(1 for v in VERDICTS if v["vision_verdict"] == "FOUNTAIN")
    # H12 v8 over-classified as FOUNTAIN_3+ (vision says MIXED, CASCADE, OTHER)
    over_classified = sum(1 for v in VERDICTS if v["vision_verdict"] in ("MIXED", "CASCADE", "OTHER (hold trick)", "OTHER (2-ball exercise)"))
    print(f"\n=== H12 v8 FOUNTAIN_3+ accuracy on visual QA ({n_qa} phases) ===")
    print(f"  H12 v8 correct (FOUNTAIN): {correct_h12v8}/{n_qa} = {correct_h12v8*100/n_qa:.1f}%")
    print(f"  H12 v8 over-classified: {over_classified}/{n_qa} = {over_classified*100/n_qa:.1f}%")
    print(f"  Visual QA: {correct_h12v8} FOUNTAIN, {sum(1 for v in VERDICTS if v['vision_verdict']=='MIXED')} MIXED, "
          f"{sum(1 for v in VERDICTS if v['vision_verdict']=='CASCADE')} CASCADE, "
          f"{sum(1 for v in VERDICTS if v['vision_verdict'] in ('OTHER (hold trick)','OTHER (2-ball exercise)'))} OTHER")

    # H39 v1 precision
    h39v1_correct_rejects = sum(1 for v in VERDICTS if v["h39v1_decision"] == "REJECTED"
                                and v["vision_verdict"] in ("OTHER (hold trick)", "OTHER (2-ball exercise)"))
    h39v1_over_rejects = sum(1 for v in VERDICTS if v["h39v1_decision"] == "REJECTED"
                              and v["vision_verdict"] in ("FOUNTAIN", "MIXED", "CASCADE"))
    h39v1_total_rejects = sum(1 for v in VERDICTS if v["h39v1_decision"] in ("REJECTED", "PARTIAL REJECT"))
    print(f"\n=== H39 v1 (frame-level) ===")
    print(f"  Correctly rejected (OTHER): {h39v1_correct_rejects}")
    print(f"  Over-rejected (real FOUNTAIN/MIXED/CASCADE): {h39v1_over_rejects}")
    print(f"  Total rejects: {h39v1_total_rejects}")
    if h39v1_total_rejects > 0:
        print(f"  Precision: {h39v1_correct_rejects}/{h39v1_total_rejects} = {h39v1_correct_rejects*100/h39v1_total_rejects:.1f}%")

    # H39 v2 precision
    h39v2_correct_rejects = sum(1 for v in VERDICTS if v["h39v2_decision"] == "REJECTED"
                                and v["vision_verdict"] in ("OTHER (hold trick)", "OTHER (2-ball exercise)"))
    h39v2_over_rejects = sum(1 for v in VERDICTS if v["h39v2_decision"] == "REJECTED"
                              and v["vision_verdict"] in ("FOUNTAIN", "MIXED", "CASCADE"))
    h39v2_total_rejects = sum(1 for v in VERDICTS if v["h39v2_decision"] == "REJECTED")
    print(f"\n=== H39 v2 (phase-level, WINDOW=0) ===")
    print(f"  Correctly rejected (OTHER): {h39v2_correct_rejects}")
    print(f"  Over-rejected (real FOUNTAIN/MIXED/CASCADE): {h39v2_over_rejects}")
    print(f"  Total rejects: {h39v2_total_rejects}")
    if h39v2_total_rejects > 0:
        print(f"  Precision: {h39v2_correct_rejects}/{h39v2_total_rejects} = {h39v2_correct_rejects*100/h39v2_total_rejects:.1f}%")


if __name__ == "__main__":
    main()
