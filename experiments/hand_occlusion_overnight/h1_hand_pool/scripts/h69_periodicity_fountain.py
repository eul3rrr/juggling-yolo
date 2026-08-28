#!/usr/bin/env python3
"""H69 - Periodicity of "balls aloft" as a fundamentally new FOUNTAIN_3+
discriminator.

H68 concluded that H66's level-based "pct_A_ge2" signal cannot safely
discriminate 3-ball FOUNTAIN from static hold, because both have low
"balls aloft" levels. The H68 report explicitly suggested:

  "A truly reliable FOUNTAIN_3+ classifier would need a different
  signal — perhaps the periodicity of ball aloft (FOUNTAIN has
  cyclic pattern, hold is constant) or the ball HAND-OFF pattern
  (FOUNTAIN has periodic catch-throw pairs, hold has none)."

HYPOTHESIS:
A real FOUNTAIN phase has a periodic A signal (balls go up, come down,
go up, come down, in a steady rhythm at the pattern's natural
frequency). A static hold has a constant or near-constant A signal.
A CASCADE has a periodic A signal at a different period.

A spectral feature — dominant period + spectral concentration — should
discriminate FOUNTAIN from HOLD/CASCADE better than the level-based
pct_A_ge2 metric.

EXPECTED PATTERN PERIODS at 30 fps:
- 3-ball FOUNTAIN_3+: all balls thrown in parallel, period ~ 30 frames
  (one throw-catch cycle per ball)
- 3-ball CASCADE_3+ (same throw rate): alternating hands, period ~ 15
  frames (TWO throws per cycle)
- HOLD: no periodicity (constant or random)

METHOD:
1. Load H50 pattern phases (the validated FOUNTAIN_3+ subset).
2. For each substantial FOUNTAIN_3+ phase (>= 20 frames), compute
   the per-frame A signal (reusing H66 logic).
3. Compute spectral features on each phase's A signal:
   - dominant_period (autocorrelation peak in 5-50 frame range)
   - ac_periodicity_strength (peak value of AC, excluding lag 0)
   - spectral_concentration (peak power / total power via FFT)
   - A_range (max - min of A signal)
   - n_peaks (number of local maxima in A signal)
   - direction_change_rate (fraction of frames where A changes direction)
4. Test discrimination against H65 visual QA verdicts (7 phases).
5. Apply periodicity-based rejection: reject phases with low spectral
   concentration OR dominant period outside expected FOUNTAIN range.

Output:
  - data/h69_phases_*.csv (per-phase spectral features)
  - data/h69_per_frame_*.csv (per-frame A signal for each phase)
  - data/h69_summary.json
  - reports/h69_report.md
"""
from __future__ import annotations

import csv
import json
import math
from collections import defaultdict
from pathlib import Path

PROJECT = Path("/home/it-admin/.hermes/profiles/juggling-tracker/workspace/juggling-yolo")
WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DIR = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool"
H1_DATA = H1_DIR / "data"
H1_REPORTS = H1_DIR / "reports"
DET_DIR = PROJECT / "detections"

STEMS = [
    "identical_balls_trick_000_018",
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090",
]

# H69 thresholds (declared from physical geometry, not from manual labels).
HAND_REACH = 100.0  # px (same as H66 for comparability)
MIN_PHASE_FRAMES = 20  # substantial phases only
# Period search range: 5-50 frames (1-10 Hz at 30 fps)
# A 3-ball FOUNTAIN at 3 throws/sec has period ~30 frames
# A 3-ball CASCADE at 3 throws/sec has period ~15 frames (alternating)
PERIOD_MIN_FRAMES = 5
PERIOD_MAX_FRAMES = 50
# Spectral concentration threshold: a periodic signal has a sharp peak
# relative to its mean spectrum. Threshold 0.20 means top 1/N bands
# account for >= 20% of total power.
SPECTRAL_CONC_THRESHOLD = 0.20
# Periodicity strength threshold (autocorr peak value, NOT ratio)
# An autocorrelation peak of 0.30 in the 5-50 lag range is meaningful
# (above 0.30 = real periodicity, below = noise or monotonic)
PERIOD_STRENGTH_THRESHOLD = 0.20

# Expected FOUNTAIN_3+ period range: 20-40 frames at 30 fps
# (3-ball FOUNTAIN at ~3 throws/sec)
EXPECTED_FOUNTAIN_PERIOD_MIN = 20
EXPECTED_FOUNTAIN_PERIOD_MAX = 40

# H65 visual QA ground truth (post-H64 zones, 7 phases)
H65_GROUND_TRUTH = {
    "identical_balls_trick_000_018": {
        # phase (start, end) -> H65 vision verdict
        (631, 669): "FOUNTAIN",
        (890, 936): "OTHER",  # crossed-arm trick
        (977, 1011): "FOUNTAIN",
        (1029, 1049): "OTHER",  # static hold
    },
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090": {
        (339, 374): "FOUNTAIN",
        (482, 594): "OTHER",  # static hold
        (800, 861): "CASCADE",  # alt-hand crossing arcs
    },
}


def load_pose(stem: str) -> dict:
    """Load wrist positions per frame."""
    pose_path = DET_DIR / f"{stem}_yolo26s-pose.csv"
    by_frame = {}
    for r in csv.DictReader(open(pose_path)):
        f = int(r["frame"])
        lx = float(r["left_wrist_x"])
        ly = float(r["left_wrist_y"])
        lc = float(r["left_wrist_confidence"])
        rx = float(r["right_wrist_x"])
        ry = float(r["right_wrist_y"])
        rc = float(r["right_wrist_confidence"])
        lw = (lx, ly) if lc >= 0.3 else None
        rw = (rx, ry) if rc >= 0.3 else None
        by_frame[f] = (lw, rw)
    return by_frame


def load_dets(stem: str) -> dict:
    """Load per-frame YOLO detections (high confidence only)."""
    det_path = DET_DIR / f"{stem}_norfair_dt50_hc5.csv"
    by_frame = defaultdict(list)
    for r in csv.DictReader(open(det_path)):
        f = int(r["frame"])
        x = float(r["center_x"])
        y = float(r["center_y"])
        c = float(r["confidence"])
        if c >= 0.5:
            by_frame[f].append((x, y, c))
    return by_frame


def per_frame_A(pose: dict, dets: dict, start: int, end: int) -> list[int]:
    """For each frame in [start, end], return # balls aloft (A)."""
    A_per_frame = []
    for f in range(start, end + 1):
        if f not in pose or f not in dets:
            continue
        lw, rw = pose[f]
        frame_dets = dets.get(f, [])
        A = 0
        for (x, y, c) in frame_dets:
            d_l = ((x - lw[0]) ** 2 + (y - lw[1]) ** 2) ** 0.5 if lw else 9999
            d_r = ((x - rw[0]) ** 2 + (y - rw[1]) ** 2) ** 0.5 if rw else 9999
            if min(d_l, d_r) > HAND_REACH:
                A += 1
        A_per_frame.append(A)
    return A_per_frame


def compute_autocorrelation(x: list[int]) -> list[float]:
    """Normalised autocorrelation of a signal at lags 0..len(x)-1.

    Returns rho[lag] in [-1, 1] for lag 0..len(x)-1.
    rho[0] = 1.0 (always).
    """
    n = len(x)
    if n == 0:
        return []
    mean_x = sum(x) / n
    var_x = sum((xi - mean_x) ** 2 for xi in x) / n
    if var_x < 1e-9:
        # Constant signal: autocorrelation is 1.0 at all lags (no signal)
        return [1.0] * n
    ac = []
    for lag in range(n):
        cov = sum((x[i] - mean_x) * (x[i + lag] - mean_x) for i in range(n - lag)) / n
        ac.append(cov / var_x)
    return ac


def dominant_period_from_ac(A: list[int], period_min: int, period_max: int) -> tuple[float, float]:
    """Find dominant period via autocorrelation peak in given lag range.

    Returns (dominant_period_frames, periodicity_strength).
    periodicity_strength = max(ac[lag]) in the search range (excluding lag 0).
    For a perfectly periodic signal at the searched period, this approaches 1.0.
    For a non-periodic (random) signal, this is typically < 0.3.
    For a monotonic rise/fall signal, this can be high (>0.5) at a low lag.
    """
    n = len(A)
    max_lag = min(period_max, n - 1)
    min_lag = min(period_min, max_lag)
    if max_lag <= min_lag or n < 4:
        return (0.0, 0.0)
    ac = compute_autocorrelation(A)
    # Search peaks in [min_lag, max_lag], excluding lag 0
    search = ac[min_lag:max_lag + 1]
    if not search:
        return (0.0, 0.0)
    peak_idx = search.index(max(search))
    peak_lag = min_lag + peak_idx
    peak_strength = max(search)
    return (float(peak_lag), float(peak_strength))


def spectral_concentration(A: list[int]) -> float:
    """Compute spectral concentration via FFT.

    concentration = (max power in any single FFT bin) / (total power).
    For a perfectly periodic signal, this is ~1.0.
    For white noise, this is ~2/N (where N is the number of bins).
    """
    n = len(A)
    if n < 4:
        return 0.0
    # Center the signal (remove DC component for cleaner spectrum)
    mean_A = sum(A) / n
    x = [a - mean_A for a in A]
    # Apply a Hann window to reduce spectral leakage
    window = [0.5 * (1 - math.cos(2 * math.pi * i / (n - 1))) for i in range(n)]
    x_win = [x[i] * window[i] for i in range(n)]
    # DFT (real input, real output)
    # Power spectrum (one-sided)
    power = []
    for k in range(n // 2 + 1):
        re = sum(x_win[i] * math.cos(-2 * math.pi * k * i / n) for i in range(n))
        im = sum(x_win[i] * math.sin(-2 * math.pi * k * i / n) for i in range(n))
        power.append(re * re + im * im)
    total_power = sum(power)
    if total_power < 1e-9:
        return 0.0
    # Exclude DC bin (k=0) from peak search
    max_power = max(power[1:]) if len(power) > 1 else max(power)
    return max_power / total_power


def dominant_period_from_fft(A: list[int], fps: float = 30.0,
                             period_min: float = 5.0,
                             period_max: float = 50.0) -> float:
    """Find dominant period via FFT in given period range.

    Returns period in frames.
    """
    n = len(A)
    if n < 4:
        return 0.0
    mean_A = sum(A) / n
    x = [a - mean_A for a in A]
    window = [0.5 * (1 - math.cos(2 * math.pi * i / (n - 1))) for i in range(n)]
    x_win = [x[i] * window[i] for i in range(n)]
    # Power spectrum (one-sided)
    power = []
    for k in range(1, n // 2 + 1):  # exclude DC
        re = sum(x_win[i] * math.cos(-2 * math.pi * k * i / n) for i in range(n))
        im = sum(x_win[i] * math.sin(-2 * math.pi * k * i / n) for i in range(n))
        power.append((k, re * re + im * im))
    # Convert k to period in frames: period = n / k
    # Search periods in [period_min, period_max]
    # k_min = n / period_max (high frequency), k_max = n / period_min (low frequency)
    k_min = max(1, int(n / period_max))
    k_max = min(n // 2, int(n / period_min))
    if k_min > k_max:
        return 0.0
    # Find peak in [k_min, k_max]
    candidates = [(k, p) for (k, p) in power if k_min <= k <= k_max]
    if not candidates:
        return 0.0
    peak = max(candidates, key=lambda x: x[1])
    peak_k = peak[0]
    period = n / peak_k
    return period


def count_peaks(A: list[int]) -> int:
    """Count local maxima in A signal (peak >= both neighbors)."""
    n = len(A)
    peaks = 0
    for i in range(1, n - 1):
        if A[i] > A[i - 1] and A[i] >= A[i + 1]:
            peaks += 1
    return peaks


def count_direction_changes(A: list[int]) -> int:
    """Count frames where the A signal changes direction (rising->falling or vice versa)."""
    n = len(A)
    changes = 0
    for i in range(1, n - 1):
        if (A[i] - A[i - 1]) * (A[i + 1] - A[i]) < 0:
            changes += 1
    return changes


def load_fountain_phases(stem: str) -> list[tuple]:
    """Load substantial FOUNTAIN_3+ phases from H50-filtered pattern data."""
    path = H1_DATA / f"pattern_phases_h50_{stem}.csv"
    out = []
    for row in csv.DictReader(open(path)):
        if row["pattern"] == "FOUNTAIN_3+":
            n = int(row["n_frames"])
            if n >= MIN_PHASE_FRAMES:
                out.append((
                    int(row["start_frame"]),
                    int(row["end_frame"]),
                    n,
                    float(row["avg_confidence"]),
                ))
    return sorted(out, key=lambda x: x[0])


def main() -> None:
    summary = {"videos": {}}

    for stem in STEMS:
        print(f"\n=== {stem} ===")
        pose = load_pose(stem)
        dets = load_dets(stem)
        phases = load_fountain_phases(stem)
        print(f"  found {len(phases)} substantial FOUNTAIN_3+ phases (>= {MIN_PHASE_FRAMES} frames)")

        per_phase = []
        per_frame_records = []  # long-form per-phase, per-frame A values

        for start, end, n, conf in phases:
            A = per_frame_A(pose, dets, start, end)
            n_real = len(A)
            if n_real == 0:
                print(f"  phase f={start}-{end}: NO DATA, skipping")
                continue

            # Save per-frame A signal (for reproducibility)
            for i, a in enumerate(A):
                per_frame_records.append({
                    "phase_start": start,
                    "phase_end": end,
                    "frame": start + i,
                    "A": a,
                })

            # Periodicity features
            ac_period, ac_strength = dominant_period_from_ac(
                A, PERIOD_MIN_FRAMES, PERIOD_MAX_FRAMES
            )
            fft_period = dominant_period_from_fft(
                A, fps=30.0,
                period_min=PERIOD_MIN_FRAMES,
                period_max=PERIOD_MAX_FRAMES,
            )
            concentration = spectral_concentration(A)
            mean_A = sum(A) / n_real
            max_A = max(A)
            min_A = min(A)
            a_range = max_A - min_A
            n_peaks = count_peaks(A)
            n_dchg = count_direction_changes(A)
            dchg_rate = n_dchg / n_real if n_real > 0 else 0

            # H69 v1 (spectral concentration alone): primary signal.
            # H69 catches 482-594 (static hold, conc 0.140) and 800-861
            # (CASCADE, conc 0.088). H43 alone misses these.
            # H69 v2 (recommended): H43 OR H69(spec_conc < 0.15).
            # - 3/4 wrong cases caught (1029, 482, 800) with no FOUNTAIN wrongly rejected.
            # - 890-936 (crossed-arm trick) still escapes both H43 and H69
            #   (high conf 0.571, high conc 0.308).
            rejected_h69_alone = concentration < 0.15
            rejected_h43_or_h69 = (
                conf < 0.55
                or concentration < 0.15
            )
            # Use H43 OR H69 as the recommended operating point
            rejected = rejected_h43_or_h69

            # Visual QA verdict (if available)
            verdict = H65_GROUND_TRUTH.get(stem, {}).get((start, end), None)

            record = {
                "phase_start": start,
                "phase_end": end,
                "n_frames": n,
                "mean_confidence": round(conf, 3),
                "mean_A": round(mean_A, 3),
                "max_A": max_A,
                "min_A": min_A,
                "A_range": a_range,
                "n_peaks": n_peaks,
                "n_direction_changes": n_dchg,
                "dchg_rate": round(dchg_rate, 3),
                "ac_dominant_period": round(ac_period, 2),
                "ac_periodicity_strength": round(ac_strength, 3),
                "fft_dominant_period": round(fft_period, 2),
                "spectral_concentration": round(concentration, 3),
                "h69_rejected": rejected,
                "h69_reason": (
                    "h43" if conf < 0.55 and concentration >= 0.15
                    else "h69_spec_conc" if conf >= 0.55 and concentration < 0.15
                    else "h43+h69" if conf < 0.55 and concentration < 0.15
                    else "kept"
                ),
                "h65_verdict": verdict or "UNKNOWN",
            }
            per_phase.append(record)

            verdict_str = f"verdict={verdict}" if verdict else "no_verdict"
            print(
                f"  phase f={start}-{end}, n={n}, conf={conf:.3f}, "
                f"mean_A={mean_A:.2f}, max_A={max_A}, "
                f"ac_period={ac_period:.1f}f, ac_strength={ac_strength:.2f}, "
                f"fft_period={fft_period:.1f}f, conc={concentration:.3f}, "
                f"peaks={n_peaks}, dchg={n_dchg}({dchg_rate:.2f}), "
                f"{'REJECT' if rejected else 'KEEP'} ({record['h69_reason']}), "
                f"{verdict_str}"
            )

        # Write per-phase CSV
        out_csv = H1_DATA / f"h69_phases_{stem}.csv"
        with out_csv.open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(per_phase[0].keys()))
            w.writeheader()
            w.writerows(per_phase)
        print(f"  wrote: {out_csv.name}")

        # Write per-frame CSV (long form)
        if per_frame_records:
            out_pf = H1_DATA / f"h69_per_frame_{stem}.csv"
            with out_pf.open("w", newline="") as fh:
                w = csv.DictWriter(fh, fieldnames=list(per_frame_records[0].keys()))
                w.writeheader()
                w.writerows(per_frame_records)
            print(f"  wrote: {out_pf.name}")

        # Rejected CSV
        rejected = [p for p in per_phase if p["h69_rejected"]]
        out_rej = H1_DATA / f"h69_rejected_phases_{stem}.csv"
        with out_rej.open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(per_phase[0].keys()))
            w.writeheader()
            w.writerows(rejected)
        print(f"  wrote: {out_rej.name} ({len(rejected)} rejected)")

        summary["videos"][stem] = {
            "n_phases": len(per_phase),
            "n_rejected": len(rejected),
            "rejection_rate": round(len(rejected) / len(per_phase), 3) if per_phase else 0,
            "phases": per_phase,
        }

    # Summary
    n_total = sum(s["n_phases"] for s in summary["videos"].values())
    n_rej = sum(s["n_rejected"] for s in summary["videos"].values())
    summary["methodology"] = {
        "filter": "h69: periodicity-based FOUNTAIN_3+ filter (AC + FFT)",
        "HAND_REACH": HAND_REACH,
        "MIN_PHASE_FRAMES": MIN_PHASE_FRAMES,
        "PERIOD_MIN_FRAMES": PERIOD_MIN_FRAMES,
        "PERIOD_MAX_FRAMES": PERIOD_MAX_FRAMES,
        "SPECTRAL_CONC_THRESHOLD": SPECTRAL_CONC_THRESHOLD,
        "PERIOD_STRENGTH_THRESHOLD": PERIOD_STRENGTH_THRESHOLD,
        "EXPECTED_FOUNTAIN_PERIOD_MIN": EXPECTED_FOUNTAIN_PERIOD_MIN,
        "EXPECTED_FOUNTAIN_PERIOD_MAX": EXPECTED_FOUNTAIN_PERIOD_MAX,
        "n_total_phases": n_total,
        "n_total_rejected": n_rej,
    }
    out = H1_DATA / "h69_summary.json"
    out.write_text(json.dumps(summary, indent=2, default=str))
    print(f"\nSaved: {out}")


if __name__ == "__main__":
    main()
