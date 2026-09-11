import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "web" / "annotation" / "fast_accept.js"
HELPERS = ROOT / "web" / "annotation" / "annotation_helpers.js"
VIEWPORT = ROOT / "web" / "annotation" / "annotation_viewport.js"
APP = ROOT / "web" / "annotation" / "app.js"
HTML = ROOT / "web" / "annotation" / "index.html"
CSS = ROOT / "web" / "annotation" / "styles.css"


def run_accept_js(body: str):
    script = f"""
const {{ prepareAccept, runAccept }} = require({json.dumps(str(MODULE))});
(async () => {{
{body}
}})().catch(error => {{ console.error(error); process.exit(1); }});
"""
    completed = subprocess.run(
        ["node", "-e", script], check=True, capture_output=True, text=True
    )
    return json.loads(completed.stdout)


def run_helpers_js(body: str):
    script = f"""
const {{ newManualBoxId }} = require({json.dumps(str(HELPERS))});
{body}
"""
    completed = subprocess.run(
        ["node", "-e", script], check=True, capture_output=True, text=True
    )
    return json.loads(completed.stdout)


def run_viewport_js(body: str):
    script = f"""
const viewport = require({json.dumps(str(VIEWPORT))});
{body}
"""
    completed = subprocess.run(
        ["node", "-e", script], check=True, capture_output=True, text=True
    )
    return json.loads(completed.stdout)


def test_zoom_viewbox_centers_at_four_x_and_clamps_all_edges():
    result = run_viewport_js("""
const values = [
  viewport.zoomViewBox(1920, 1080, 960, 540, 4),
  viewport.zoomViewBox(1920, 1080, 0, 0, 4),
  viewport.zoomViewBox(1920, 1080, 1920, 540, 4),
  viewport.zoomViewBox(1920, 1080, 960, 1080, 4),
];
console.log(JSON.stringify(values));
""")
    assert result == [
        {"x": 720, "y": 405, "width": 480, "height": 270},
        {"x": 0, "y": 0, "width": 480, "height": 270},
        {"x": 1440, "y": 405, "width": 480, "height": 270},
        {"x": 720, "y": 810, "width": 480, "height": 270},
    ]


def test_fit_and_add_stage_state_are_explicit():
    result = run_viewport_js("""
const picked = viewport.pickAddCenter(1920, 1080, [12, 34], 4);
console.log(JSON.stringify({fit:viewport.fitViewBox(1920,1080),start:viewport.startAdd(),picked}));
""")
    assert result["fit"] == {"x": 0, "y": 0, "width": 1920, "height": 1080}
    assert result["start"] == {"mode": "add", "addStage": "pick-center"}
    assert result["picked"]["mode"] == "add"
    assert result["picked"]["addStage"] == "draw"
    assert result["picked"]["viewBox"] == {"x": 0, "y": 0, "width": 480, "height": 270}


def test_labels_are_hidden_while_adding_but_restored_in_select_mode():
    app = APP.read_text()
    assert "if(state.mode==='select')" in app
    assert "text.textContent=shortId(b)" in app


def test_viewport_workflow_is_wired_without_css_canvas_zoom():
    app = APP.read_text()
    html = HTML.read_text()
    assert "AnnotationViewport.zoomViewBox" in app
    assert "addStage==='pick-center'" in app
    assert "viewBox" in app
    assert "canvas.style.width" not in app
    assert 'id="fit"' in html
    assert 'src="/annotation_viewport.js"' in html


def test_manual_box_ids_are_unique_within_item_and_fill_first_gap():
    result = run_helpers_js("""
const boxes = [{id:'manual-1'}, {id:'detector-a'}, {id:'manual-3'}];
const first = newManualBoxId(boxes);
boxes.push({id:first});
const second = newManualBoxId(boxes);
console.log(JSON.stringify({first,second}));
""")
    assert result == {"first": "manual-2", "second": "manual-4"}


def test_basic_annotation_has_no_secure_context_uuid_dependency():
    app = APP.read_text()
    helpers = HELPERS.read_text()
    assert "crypto.randomUUID" not in app
    assert "crypto.randomUUID" not in helpers
    assert "AnnotationHelpers.newManualBoxId(state.item.boxes)" in app


def test_accept_untouched_frame_preserves_boxes_and_optional_metadata():
    result = run_accept_js("""
const item = {
  priority: 0,
  focus_status: '',
  focus_box_id: null,
  boxes: [{id:'a',x1:1,y1:2,x2:3,y2:4,visibility:''}],
  all_visible_confirmed: false,
};
const prepared = prepareAccept(item);
console.log(JSON.stringify({prepared, unchanged: item.all_visible_confirmed === false}));
""")
    assert result["prepared"]["boxes"][0]["visibility"] == ""
    assert result["prepared"]["focus_status"] == ""
    assert result["prepared"]["all_visible_confirmed"] is True
    assert result["unchanged"] is True


def test_accept_dirty_edited_frame_saves_completed_and_advances():
    result = run_accept_js("""
const item = {id:'i',revision:2,boxes:[{id:'a',x1:9,y1:2,x2:30,y2:40}],all_visible_confirmed:false};
const calls=[];
const ok=await runAccept({item,save:async (...args)=>calls.push(args)});
console.log(JSON.stringify({ok,calls}));
""")
    assert result["ok"] is True
    assert result["calls"][0][0:2] == ["completed", True]
    assert result["calls"][0][2]["boxes"][0]["x1"] == 9
    assert result["calls"][0][2]["all_visible_confirmed"] is True


def test_accept_zero_box_frame():
    result = run_accept_js("""
console.log(JSON.stringify(prepareAccept({boxes:[],all_visible_confirmed:false,focus_status:''})));
""")
    assert result["boxes"] == []
    assert result["all_visible_confirmed"] is True


def test_pointer_editor_is_pen_touch_mouse_neutral():
    app = APP.read_text()
    assert "pointerdown" in app
    assert "pointermove" in app
    assert "pointerup" in app
    assert "setPointerCapture" in app
    assert "mousedown" not in app
    assert "mousemove" not in app
    assert "pointerType" not in app  # no pen/touch/mouse filtering or branching


def test_normal_ui_requires_no_focus_or_survey_interaction():
    html = HTML.read_text()
    normal, advanced = html.split('<details id="advanced">', 1)
    for hidden_term in ("focus ball", "linked gaps", "unresolved boundaries", "survey", "occluder", "motion blur"):
        assert hidden_term not in normal.lower()
    assert 'id="fastAccept"' in normal
    assert 'Accept &amp; Next (G)' in normal
    assert 'id="survey"' in advanced
    assert 'id="focus"' in advanced


def test_resize_handles_use_svg_transform_for_css_sized_touch_targets():
    app = APP.read_text()
    assert "getScreenCTM()" in app
    assert "1/Math.abs(transform.a)" in app
    assert "1/Math.abs(transform.d)" in app
    assert "30*unitX" in app and "30*unitY" in app


def test_tablet_editor_disables_touch_gestures_without_disabling_page_scroll():
    css = CSS.read_text()
    assert "#canvas" in css
    canvas_rule = css.split("#canvas", 1)[1].split("}", 1)[0]
    assert "touch-action:none" in canvas_rule
    assert "user-select:none" in canvas_rule
    assert "body{touch-action:none" not in css
