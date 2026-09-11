import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "web" / "annotation" / "fast_accept.js"


def run_fast_accept_js(body: str):
    script = f"""
const {{ inferFocusBox, prepareFastAccept, runFastAccept }} = require({json.dumps(str(MODULE))});
(async () => {{
{body}
}})().catch(error => {{ console.error(error); process.exit(1); }});
"""
    completed = subprocess.run(
        ["node", "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def test_one_containing_box_is_selected():
    result = run_fast_accept_js("""
const result = inferFocusBox([15, 15], [
  {id: 'far', x1: 30, y1: 30, x2: 40, y2: 40},
  {id: 'hit', x1: 10, y1: 10, x2: 20, y2: 20},
]);
console.log(JSON.stringify(result));
""")
    assert result == {"ok": True, "boxId": "hit"}


def test_zero_boxes_cannot_infer_visible_focus():
    result = run_fast_accept_js("""
console.log(JSON.stringify(inferFocusBox([15, 15], [])));
""")
    assert result["ok"] is False
    assert "no unambiguous focus box" in result["error"]


def test_overlapping_containing_boxes_are_ambiguous():
    result = run_fast_accept_js("""
console.log(JSON.stringify(inferFocusBox([15, 15], [
  {id: 'a', x1: 10, y1: 10, x2: 20, y2: 20},
  {id: 'b', x1: 12, y1: 12, x2: 22, y2: 22},
])));
""")
    assert result["ok"] is False
    assert "multiple candidate focus boxes" in result["error"]


def test_ordinary_control_prepares_every_box_and_confirmation():
    result = run_fast_accept_js("""
const item = {
  priority: 2,
  focus_status: '',
  focus_box_id: 'old',
  all_visible_confirmed: false,
  boxes: [
    {id: 'a', x1: 1, y1: 2, x2: 3, y2: 4, occluder: ''},
    {id: 'b', x1: 5, y1: 6, x2: 7, y2: 8, visibility: 'partial'},
  ],
};
const beforeGeometry = item.boxes.map(({x1,y1,x2,y2}) => [x1,y1,x2,y2]);
const result = prepareFastAccept(item, false);
console.log(JSON.stringify({result, beforeGeometry}));
""")
    prepared = result["result"]["item"]
    assert prepared["focus_status"] == "not_applicable"
    assert prepared["focus_box_id"] is None
    assert prepared["all_visible_confirmed"] is True
    assert [[b[k] for k in ("x1", "y1", "x2", "y2")] for b in prepared["boxes"]] == result["beforeGeometry"]
    for box in prepared["boxes"]:
        assert box | {
            "occluder": "none",
            "occlusion": "none",
            "visibility": "clear",
            "motion_blur": "none",
            "annotation_confidence": "certain",
        } == box


def test_zero_box_ordinary_control_is_valid():
    result = run_fast_accept_js("""
console.log(JSON.stringify(prepareFastAccept({priority: 2, boxes: [], all_visible_confirmed: false}, false)));
""")
    assert result["ok"] is True
    assert result["item"]["boxes"] == []
    assert result["item"]["all_visible_confirmed"] is True


def test_dirty_frame_refuses_without_mutating_item():
    result = run_fast_accept_js("""
const item = {priority: 2, boxes: [{id: 'a', visibility: 'partial'}], all_visible_confirmed: false};
const before = JSON.stringify(item);
const result = prepareFastAccept(item, true);
console.log(JSON.stringify({result, unchanged: before === JSON.stringify(item)}));
""")
    assert result["result"]["ok"] is False
    assert "unsaved edits" in result["result"]["error"]
    assert result["unchanged"] is True


def test_success_saves_completed_and_advances():
    result = run_fast_accept_js("""
const calls = [];
const messages = [];
const ok = await runFastAccept({
  item: {priority: 2, boxes: []},
  dirty: false,
  save: async (...args) => calls.push(args),
  message: text => messages.push(text),
});
console.log(JSON.stringify({ok, calls, messages}));
""")
    assert result["ok"] is True
    assert result["calls"][0][0:2] == ["completed", True]
    assert result["calls"][0][2]["all_visible_confirmed"] is True


def test_failed_focus_inference_does_not_save_or_mutate():
    result = run_fast_accept_js("""
const item = {priority: 1, focus_point: [50, 50], boxes: [{id: 'a', x1: 0, y1: 0, x2: 10, y2: 10}]};
const before = JSON.stringify(item);
let saves = 0;
const messages = [];
const ok = await runFastAccept({
  item,
  dirty: false,
  save: async () => { saves += 1; },
  message: text => messages.push(text),
});
console.log(JSON.stringify({ok, saves, messages, unchanged: before === JSON.stringify(item)}));
""")
    assert result["ok"] is False
    assert result["saves"] == 0
    assert result["unchanged"] is True
    assert "manual focus review" in result["messages"][0]
