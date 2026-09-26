'use strict';
/* Vision-stitch review UI: model verdict + evidence + human label.
   The player loops inside the event window and never auto-advances. */

const state = { items: [], visible: [], index: 0, playing: false, frame: 0, window: null, timer: null };

const $ = (id) => document.getElementById(id);

function pct(v) { return v === null || v === undefined ? '–' : Math.round(v * 100) + '%'; }

function decisionClass(decision) {
  return decision === 'stitch' ? 'stitch' : decision === 'none' ? 'none' : 'uncertain';
}

function candidateRows(item) {
  const rows = item.candidates.map((c) => {
    const classes = [];
    if (item.model.candidate_letter === c.letter) classes.push('chosen');
    if (item.cv_rank1 && item.cv_rank1.track_id === c.track_id) classes.push('cv');
    return `<tr class="${classes.join(' ')}">
      <td><b>${c.letter}</b></td>
      <td>T${c.track_id}</td>
      <td>${c.first_frame} (${(c.first_frame / item.window.fps).toFixed(2)}s)</td>
      <td>${c.gap_frames}f / ${c.gap_seconds.toFixed(2)}s</td>
      <td>${Math.round(c.prediction_error)} px</td>
      <td>${c.observed_len}</td></tr>`;
  }).join('');
  return `<thead><tr><th></th><th>tracklet</th><th>starts frame (s)</th><th>gap</th><th>CV error</th><th>obs len</th></tr></thead>
    <tbody>${rows}</tbody>`;
}

function render() {
  const item = state.visible[state.index];
  $('position').textContent = item
    ? `event ${state.index + 1}/${state.visible.length}` : 'no events match the filters';
  $('labelled').textContent = `labelled ${state.items.filter((i) => i.label).length}/${state.items.length}`;
  const labelled = state.items.filter((i) => i.label && i.model.decision);
  const agree = labelled.filter((i) => labelAgrees(i)).length;
  $('agreement').textContent = labelled.length
    ? `vision vs you: ${agree}/${labelled.length} (${Math.round(100 * agree / labelled.length)}%)` : 'vision vs you: –';
  if (!item) { $('images').innerHTML = ''; $('verdictBox').textContent = '–'; $('cvBox').textContent = '–';
    $('candidates').innerHTML = ''; $('stage').getContext('2d').clearRect(0, 0, 960, 540); return; }

  $('images').innerHTML = item.images.map((image) => {
    const cls = image.role === 'context' ? 'ctx' : image.role === 'candidate' ? 'cand' : 'src';
    const tag = image.letter ? `CAND-${image.letter}` : image.role.replace('source_', 'END ');
    return `<figure class="${cls}" data-src="${image.url}">
      <img loading="lazy" src="${image.url}" alt="${image.label}">
      <figcaption><b>${tag}</b> · t=${image.seconds.toFixed(2)}s · f${image.frame}<br>${image.label}</figcaption>
    </figure>`;
  }).join('');

  const m = item.model;
  $('verdictBox').innerHTML = m.judged
    ? `<div class="decision ${decisionClass(m.decision)}">${m.decision}${m.candidate_letter ? ' → ' + m.candidate_letter : ''}
        ${m.candidate_track_id ? `(T${m.candidate_track_id})` : ''}</div>
       <div class="conf">confidence ${pct(m.confidence)} · ${m.model || ''} · ${m.latency_s ? m.latency_s.toFixed(1) + 's' : ''}
        ${m.parse_ok ? '' : ' · <span style="color:#f85149">parse failure</span>'}</div>
       <div class="reason">${m.reason ? m.reason : '<i>no reason given</i>'}</div>
       ${m.error ? `<div class="conf" style="color:#f85149">${m.error}</div>` : ''}`
    : '<i>not judged yet — run the judge step for this event</i>';

  const cv = item.cv_rank1;
  $('cvBox').innerHTML = `<div>constant-velocity rank-1 → <b>T${cv.track_id}</b>
      (prediction error ${Math.round(cv.prediction_error)} px, gap ${cv.gap_frames}f)</div>
    <div class="conf">${m.judged && m.decision === 'stitch'
      ? (m.candidate_track_id === cv.track_id ? 'model agrees with the geometric rank-1' : 'model differs from the geometric rank-1')
      : 'the stitcher would propose this candidate'}</div>`;
  $('candidates').innerHTML = candidateRows(item);

  $('note').value = item.label ? item.label.note || '' : '';
  $('savedState').textContent = item.label ? `saved: ${item.label.label}` : '';

  state.window = item.window;
  state.frame = state.window.reference_frame;
  $('scrub').min = state.window.first_frame;
  $('scrub').max = state.window.last_frame;
  $('scrub').value = state.frame;
  drawFrame();
}

/* The human label grades the model's verdict: 'correct' means the verdict was
   right (stitch or decline), 'wrong' means it was wrong, 'unclear' abstains. */
function labelAgrees(item) {
  return Boolean(item.label && item.label.label === 'correct');
}

async function drawFrame() {
  const item = state.visible[state.index];
  if (!item) return;
  const url = `/frame?event=${encodeURIComponent(item.slug)}&frame=${state.frame}`;
  const image = new Image();
  image.onload = () => {
    const canvas = $('stage');
    canvas.width = image.width;
    canvas.height = image.height;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(image, 0, 0);
    ctx.font = '22px monospace';
    ctx.fillStyle = '#000000aa';
    ctx.fillRect(0, 0, 400, 34);
    ctx.fillStyle = '#e6edf3';
    ctx.fillText(`f${state.frame}  t=${(state.frame / item.window.fps).toFixed(2)}s`, 8, 25);
  };
  image.src = url;
  $('frameInfo').textContent = `f${state.frame} · ${(state.frame / item.window.fps).toFixed(2)}s`;
  $('scrub').value = state.frame;
}

function tick() {
  const item = state.visible[state.index];
  if (!item || !state.playing) return;
  if (state.frame >= state.window.last_frame) {
    state.frame = state.window.first_frame;      // loop, never advance the event
  } else {
    state.frame += 2;
  }
  drawFrame();
}

function setPlaying(on) {
  state.playing = on;
  if (state.timer) { clearInterval(state.timer); state.timer = null; }
  if (on) state.timer = setInterval(tick, 90);
}

function move(delta) {
  if (!state.visible.length) return;
  state.index = Math.min(state.visible.length - 1, Math.max(0, state.index + delta));
  setPlaying(false);
  render();
}

async function saveLabel(label) {
  const item = state.visible[state.index];
  if (!item || !label) return;
  try {
    const response = await fetch('/api/label', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ event_key: item.event_key, label, note: $('note').value }),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || 'save failed');
    item.label = payload.label;
    $('savedState').textContent = `saved: ${payload.label.label}`;
  } catch (error) {
    $('savedState').textContent = `not saved: ${error.message}`;
    return;
  }
  applyFilters();
  if (state.index >= state.visible.length) state.index = Math.max(0, state.visible.length - 1);
  setPlaying(false);
  render();
}

function applyFilters() {
  const decision = $('filterDecision').value;
  const agreement = $('filterAgreement').value;
  const minConf = parseFloat($('filterConfidence').value);
  const unlabelledOnly = $('filterUnlabelled').checked;
  state.visible = state.items.filter((item) => {
    const m = item.model;
    if (decision === 'unjudged' && m.judged) return false;
    if (decision !== 'all' && decision !== 'unjudged' && m.decision !== decision) return false;
    if ((m.confidence || 0) < minConf && m.judged) return false;
    if (agreement !== 'all') {
      if (m.decision !== 'stitch' || !item.cv_rank1) return false;
      const same = m.candidate_track_id === item.cv_rank1.track_id;
      if (agreement === 'same' && !same) return false;
      if (agreement === 'different' && same) return false;
    }
    if (unlabelledOnly && item.label) return false;
    return true;
  });
  if (state.index >= state.visible.length) state.index = 0;
}

async function load() {
  const response = await fetch('/api/items');
  const payload = await response.json();
  state.items = payload.items;
  $('videoName').textContent = payload.video || '';
  applyFilters();
  render();
}

document.addEventListener('keydown', (event) => {
  if (event.target.matches('textarea, input, select')) return;
  const key = event.key;
  if (key === 'c') return void saveLabel('correct');
  if (key === 'w') return void saveLabel('wrong');
  if (key === 'u') return void saveLabel('unclear');
  if (key === 's') return void move(1);
  if (key === 'n' || key === 'ArrowDown') return void move(1);
  if (key === 'p' || key === 'ArrowUp') return void move(-1);
  if (key === ' ') { event.preventDefault(); return void setPlaying(!state.playing); }
  if (key === 'ArrowRight') { state.frame = Math.min(state.window.last_frame, state.frame + 2); return void drawFrame(); }
  if (key === 'ArrowLeft') { state.frame = Math.max(state.window.first_frame, state.frame - 2); return void drawFrame(); }
  if (key === 'r') { state.frame = state.window.reference_frame; return void drawFrame(); }
});

$('prev').onclick = () => move(-1);
$('next').onclick = () => move(1);
$('play').onclick = () => setPlaying(!state.playing);
$('stepBack').onclick = () => { state.frame = Math.max(state.window.first_frame, state.frame - 2); drawFrame(); };
$('stepFwd').onclick = () => { state.frame = Math.min(state.window.last_frame, state.frame + 2); drawFrame(); };
$('restart').onclick = () => { state.frame = state.window.reference_frame; drawFrame(); };
$('scrub').oninput = (event) => { state.frame = parseInt(event.target.value, 10); drawFrame(); };
$('skip').onclick = () => move(1);
for (const button of document.querySelectorAll('button[data-label]')) {
  button.onclick = () => saveLabel(button.dataset.label);
}
for (const control of document.querySelectorAll('#filterDecision, #filterAgreement, #filterConfidence, #filterUnlabelled')) {
  control.onchange = () => { applyFilters(); render(); };
}
$('images').onclick = (event) => {
  const figure = event.target.closest('figure');
  if (!figure) return;
  const dialog = document.createElement('dialog');
  dialog.innerHTML = `<img src="${figure.dataset.src}" alt="">`;
  dialog.onclick = () => dialog.close();
  document.body.appendChild(dialog);
  dialog.showModal();
};

load();
