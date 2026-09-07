# Frozen demo hand CSV reproduction

This publishes the existing boundary → logical event → FIFO hand producer, **not
an algorithm update**. The three shipped CSVs reproduce **byte-for-byte** from
the canonical YOLO26l tracklets and the historical augmented pose input. No
thresholds, decisions, inference, source videos, or rendered media are changed.

## Important input limitation

`detections/identical_balls_trick_000_018_yolo26s-pose.csv` is **not** the pose input
that produced the demo. It has raw wrist coordinates only, no
`left_wrist_x_smooth` / `right_wrist_x_smooth` or `body_scale_shoulder_px` columns.
It contains 1084 rows. The historical `yolo26s-pose-hands.csv` contains 1086 rows,
smoothed keypoints and shoulder scale, and different underlying inference
values (already different on frame 0). This is not a filename-only distinction.
The unchanged loader given the wrist-only CSV produces no eligible hand
boundaries; the regression explicitly records this incompatibility.

Consequently, **exact regeneration from only the existing wrist-only pose CSV
and tracklets is not supported**. Deriving the missing pose evidence would
require a different algorithm or new inference, neither of which is done here.
Instead the exact previously committed augmented pose bytes are restored as a
new support fixture:

`tests/fixtures/demo_hand/identical_balls_trick_000_018_yolo26s-pose-hands.csv`

The fixture retains historical `video` metadata strings, including absolute
paths. They are provenance, not paths opened by this producer. No clip is needed.

## Reproduce safely

Run from the repository root with Python >=3.10 and NumPy. Verification uses
pytest. The observed environment was Python **3.14.4**, NumPy **1.26.4**, pytest
**9.1.1**; the hand-only path does not import OpenCV, Torch or Ultralytics.
Use the existing `.venv` (no dependency installation is needed there).

```bash
out=$(mktemp -d /tmp/demo-hand.XXXXXX)
.venv/bin/python scripts/reproduce_demo_hand.py --output-dir "$out"
```

The helper refuses nonempty output directories, executes all three historical
stages from the CSV inputs, and compares every byte of all three results against
`detections/demo/`. Any mismatch fails; no tolerance, ignored columns, substituted
expected rows, or post-generation patch is used. It also emits boundary
assessments and unmatched-event diagnostics to the same temporary directory.

For the explicit historical stage CLIs (use a **new** temporary directory; these
original CLIs do not have the helper's overwrite guard):

```bash
out=$(mktemp -d /tmp/demo-hand-stages.XXXXXX)
stem=identical_balls_trick_000_018
.venv/bin/python scripts/hand_boundaries.py \
  --tracklets "detections/demo/${stem}_yolo26l_classes-32_norfair_dt50_hc5.csv" \
  --hands "tests/fixtures/demo_hand/${stem}_yolo26s-pose-hands.csv" \
  --output-csv "$out/${stem}_hand_boundary_assessments.csv"
.venv/bin/python scripts/hand_events.py \
  --assessments "$out/${stem}_hand_boundary_assessments.csv" \
  --frame-min 2 --frame-max 1078 \
  --output-csv "$out/${stem}_hand_events.csv"
.venv/bin/python scripts/hand_state_machine.py \
  --events "$out/${stem}_hand_events.csv" \
  --fps 59.94005994 --output-dir "$out"
for suffix in hand_events hand_associations hand_state_trace; do
  cmp "detections/demo/${stem}_${suffix}.csv" "$out/${stem}_${suffix}.csv"
done
```

`2..1078` is the observed-tracklet range used for historical boundary flags.
The exact FPS `59.94005994` is recovered from the shipped `hold_seconds` values
and verified against every association row. Rounding it to `59.94` keeps the
same decisions and trace, but changes all six `hold_seconds` strings. For
example, the first becomes `0.05005005005005005` instead of the shipped
`0.050050000000050054`. Even `60000/1001` should not replace the serialized
historical FPS when byte identity is required. This is a reproduction parameter,
not threshold tuning. FIFO retains its unchanged default five-second expiry.

## Exact source provenance

Source tree: `232555bdf4d2e1a3ebedd35851285ca07097ea45` on the historical
`experiment/detector-segmentation-capacity` lineage. Its FIFO parent is
`612806830aa4c736d785af13e4437c1f0e33c421`. Across those two commits the only change
to the three producer modules is removing the unused `load_logical_events`
import from `hand_state_machine.py`; boundary/event logic is identical.

All six modules below are copied **unchanged** from `232555b...`, at the same
`scripts/` paths. Full Git blob IDs permit content verification:

| File | Original Git blob SHA-1 |
| --- | --- |
| `hand_boundaries.py` | `07593dc036b715bce6fb2760eb66c381f17a6591` |
| `hand_events.py` | `25c0f5afbbbc5a4c4572a67fccd24137f3336e17` |
| `hand_state_machine.py` | `a30a571b105a8390be55ecb891b03e948cf72722` |
| `hand_association.py` | `e9136a456a31a9d4fe5d15320a2840552159ba61` |
| `hand_features.py` | `b64c92dba13b9d313bf898c813472ca51cb326b6` |
| `hand_overlay.py` | `8855d308f5f6902b4de126f48d37ee22beaffe16` |

The last three are the original import dependency closure. `hand_boundaries`
uses the association module's configuration/data/loading/numerical helpers,
**not** its legacy high-level classifier or old queue engine. `hand_overlay` is
loaded by its existing import helper; it renders nothing here. Keeping whole
modules preserves exact provenance rather than refactoring their internals.

The six corresponding `tests/test_hand_*.py` files also originate at
`232555b...`. Only `test_hand_state_machine.py` differs: its historical
`detections/detector_seg_comparison/` reference is changed to `detections/demo/`.
Its assertions and original `59.94` invariant-test FPS are unchanged. The helper,
`tests/test_reproduce_demo_hand.py`, and this document are new glue/tests/docs.

### Input hashes (SHA-256)

The tracklet CSV and wrist-only pose CSV match their historical source bytes.
The fixture is an unchanged copy of
`232555b...:detections/identical_balls_trick_000_018_yolo26s-pose-hands.csv`.

| Input | SHA-256 |
| --- | --- |
| Canonical YOLO26l `..._norfair_dt50_hc5.csv` | `daa7905eac1ec6bc9b96c4c9ea791fbbc4673d0b3a6533b771a39798a066569b` |
| Historical augmented pose fixture | `5ddb7d426e934f4f7bc288969c8d93a54be582a0a630d0ab54343f5ac5a8f843` |
| Wrist-only pose (incompatible, not used for reproduction) | `0d273faf9bd68c1f9e543405fb902dd05c5d25a26fca66f39c544cf2531211fc` |

### Frozen output hashes (SHA-256)

All three shipped outputs are identical to their `232555b...` versions under
`detections/detector_seg_comparison/`. All three generated outputs match:

| Suffix after `identical_balls_trick_000_018_` | Data rows | SHA-256 |
| --- | ---: | --- |
| `hand_events.csv` | 28 | `9fdb297f1da0715be4ff79a78b57e072edae0d9cd559e59c2bad98109e6c75e2` |
| `hand_associations.csv` | 6 | `2bf9e3512322ce14adac6a830a952734a009cfd1b10beb584c95753f14ee97e4` |
| `hand_state_trace.csv` | 19 | `8d6e7de04807d1d845b816ddd12c385f659f339703604fd8f2518649304f1398` |

The six associations in emitted order are `3→4`, `1→5`, `4→6`, `5→10`, `2→11`,
`6→13`. Reproduction preserves these existing decisions; it is not a claim that
every physical hand transition has been correctly detected.

## Regression

```bash
.venv/bin/python -m pytest -o addopts='' -q tests/test_hand_*.py tests/test_reproduce_demo_hand.py
.venv/bin/python -m pytest -o addopts='' -q tests/
```

The new end-to-end test runs the real CLI in a subprocess into pytest's
`tmp_path`, generating boundaries from canonical tracklets + the restored
historical augmented pose, then events and FIFO outputs. It requires byte
identity for **all columns and rows** in all three shipped CSVs. Separate tests
pin input hashes, expose the wrist-only pose limitation, and prevent output
clobbering. Run the full suite above to include the documentation and frozen-media checks.
