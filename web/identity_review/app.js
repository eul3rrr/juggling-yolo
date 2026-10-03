// Ball identity review: review video + per-ball state timeline + link list with labels.
(() => {
  const PALETTE = ["#ff3c3c", "#3cdc3c", "#2896ff", "#ffdc28", "#dc3cff", "#50ffff", "#ff5a96", "#c8c8c8"];
  const KIND_COLOR = { hidden: "#f85149", hand: "#3fb950", flight: "#58a6ff", near: "#d29922" };
  const $ = (id) => document.getElementById(id);
  const video = $("video");
  const canvas = $("timeline");
  const state = { data: null, segment: null, links: [], current: null, speed: 1, raf: 0 };

  const ballColor = (ball) => PALETTE[(ball - 1) % PALETTE.length];
  const fmt = (s) => `${Math.floor(s / 60)}:${(s % 60).toFixed(2).padStart(5, "0")}`;

  // --- time mapping: the review video holds only frames inside the processed segments
  function segmentOf(frame) {
    return state.data.segments.find((s) => s.video_offset !== null && frame >= s.first_frame && frame <= s.last_frame);
  }
  function timeOfFrame(frame, seg = segmentOf(frame)) {
    if (!seg) return 0;
    return (seg.video_offset + frame - seg.first_frame) / state.data.fps;
  }
  function frameAtTime(t) {
    const idx = Math.round(t * state.data.fps);
    for (const s of state.data.segments) {
      if (s.video_offset === null) continue;
      const length = s.last_frame - s.first_frame + 1;
      if (idx >= s.video_offset && idx < s.video_offset + length) return { seg: s, frame: s.first_frame + idx - s.video_offset };
    }
    return { seg: null, frame: null };
  }
  function seekFrame(frame, play = false) {
    video.currentTime = timeOfFrame(frame) + 0.0001;
    if (play) video.play(); else video.pause();
  }

  // --- segment selection
  function selectSegment(index, seek = true) {
    const seg = state.data.segments.find((s) => s.segment_index === index);
    if (!seg || seg.video_offset === null) return;
    state.segment = seg;
    $("segmentSelect").value = String(index);
    $("segmentInfo").textContent = `segment ${index} · ${seg.ball_count} balls (${seg.ball_count_source}) · gravity ${seg.accel_y_px_per_frame2 ? seg.accel_y_px_per_frame2.toFixed(2) : "–"} px/f² (${seg.accel_source})`;
    document.querySelectorAll("#segmentTable tr").forEach((tr) => tr.classList.toggle("active", tr.dataset.segment === String(index)));
    if (seek) seekFrame(seg.first_frame);
    drawTimeline();
    renderLinks();
  }

  // --- timeline
  function drawTimeline() {
    const seg = state.segment;
    if (!seg) return;
    const rowH = 22, top = 4, left = 28, bottom = 16;
    const width = canvas.clientWidth || 800;
    const height = top + rowH * seg.balls.length + bottom;
    canvas.width = width * devicePixelRatio;
    canvas.height = height * devicePixelRatio;
    canvas.style.height = `${height}px`;
    const ctx = canvas.getContext("2d");
    ctx.scale(devicePixelRatio, devicePixelRatio);
    ctx.clearRect(0, 0, width, height);
    const span = seg.last_frame - seg.first_frame + 1;
    const x = (frame) => left + ((frame - seg.first_frame) / span) * (width - left - 4);
    seg.balls.forEach((ball, i) => {
      const y = top + i * rowH;
      const color = ballColor(ball.ball_id);
      ctx.fillStyle = color;
      ctx.font = "bold 12px sans-serif";
      ctx.fillText(String(ball.ball_id), 8, y + 15);
      for (const [start, end, kind, hand] of ball.runs) {
        const x0 = x(start), x1 = Math.max(x(end + 1), x0 + 1);
        if (kind === "HIDDEN") {
          ctx.fillStyle = "#2a2f36";
          ctx.fillRect(x0, y + 4, x1 - x0, rowH - 8);
          continue;
        }
        ctx.globalAlpha = kind === "PREDICTED" ? 0.4 : 1;
        ctx.fillStyle = color;
        ctx.fillRect(x0, y + 3, x1 - x0, rowH - 6);
        ctx.globalAlpha = 1;
        if (kind === "HELD") {
          ctx.save();
          ctx.beginPath(); ctx.rect(x0, y + 3, x1 - x0, rowH - 6); ctx.clip();
          ctx.strokeStyle = "rgba(0,0,0,0.55)"; ctx.lineWidth = 2;
          for (let k = x0 - rowH; k < x1 + rowH; k += 6) { ctx.beginPath(); ctx.moveTo(k, y + rowH); ctx.lineTo(k + rowH, y); ctx.stroke(); }
          ctx.restore();
          if (hand && x1 - x0 > 14) {
            ctx.fillStyle = "#000"; ctx.font = "bold 10px sans-serif";
            ctx.fillText(hand[0], x0 + 3, y + 14);
          }
        }
      }
    });
    for (const link of state.data.links) {
      if (link.segment_index !== seg.segment_index) continue;
      const row = seg.balls.findIndex((b) => b.ball_id === link.ball_id);
      if (row < 0) continue;
      const px = x(link.target_start_frame), y = top + row * rowH;
      ctx.fillStyle = KIND_COLOR[link.kind] || "#fff";
      ctx.beginPath(); ctx.moveTo(px, y + rowH - 9); ctx.lineTo(px - 5, y + rowH - 1); ctx.lineTo(px + 5, y + rowH - 1); ctx.closePath(); ctx.fill();
      if (state.current && state.current.link_key === link.link_key) {
        ctx.strokeStyle = "#fff"; ctx.lineWidth = 1.5; ctx.strokeRect(px - 7, y + 1, 14, rowH - 2);
      }
    }
    ctx.fillStyle = "#8b949e"; ctx.font = "11px sans-serif";
    const seconds = span / state.data.fps;
    const step = seconds > 60 ? 10 : seconds > 20 ? 5 : 1;
    for (let s = 0; s <= seconds; s += step) {
      const px = x(seg.first_frame + s * state.data.fps);
      ctx.fillRect(px, height - bottom, 1, 4);
      ctx.fillText(`${(seg.first_frame / state.data.fps + s).toFixed(0)}s`, px - 8, height - 3);
    }
    drawPlayhead();
  }
  function drawPlayhead() {
    const seg = state.segment;
    if (!seg) return;
    const { frame } = frameAtTime(video.currentTime);
    const ctx = canvas.getContext("2d");
    const width = canvas.clientWidth || 800;
    if (frame === null || frame < seg.first_frame || frame > seg.last_frame) return;
    const span = seg.last_frame - seg.first_frame + 1;
    const px = 28 + ((frame - seg.first_frame) / span) * (width - 32);
    ctx.fillStyle = "rgba(255,255,255,0.85)";
    ctx.fillRect(px, 0, 1.5, canvas.height / devicePixelRatio - 16);
  }
  canvas.addEventListener("click", (e) => {
    const seg = state.segment;
    if (!seg) return;
    const rect = canvas.getBoundingClientRect();
    const span = seg.last_frame - seg.first_frame + 1;
    const frac = (e.clientX - rect.left - 28) / (rect.width - 32);
    seekFrame(Math.round(seg.first_frame + Math.min(1, Math.max(0, frac)) * span));
  });

  // --- links
  function visibleLinks() {
    const kind = $("filterKind").value;
    const onlySeg = $("filterSegment").checked;
    const unlabelled = $("filterUnlabelled").checked;
    return state.data.links.filter((l) =>
      (kind === "all" || l.kind === kind) &&
      (!onlySeg || !state.segment || l.segment_index === state.segment.segment_index) &&
      (!unlabelled || !l.label));
  }
  function renderLinks() {
    state.links = visibleLinks();
    const list = $("linkList");
    list.innerHTML = "";
    for (const link of state.links) {
      const li = document.createElement("li");
      li.dataset.key = link.link_key;
      li.classList.toggle("active", state.current && state.current.link_key === link.link_key);
      li.innerHTML = `<span>${fmt(parseFloat(link.source_end_seconds))}</span>` +
        `<span class="ball" style="color:${ballColor(link.ball_id)}">● ${link.ball_id}</span>` +
        `<span class="badge ${link.kind}">${link.kind}</span>` +
        `<span class="detail">track ${link.source_track_id} → ${link.target_track_id}${link.hand ? " · " + link.hand.toLowerCase() : ""} · gap ${link.gap_frames} f · seg ${link.segment_index}</span>` +
        `<span class="detail">cost ${link.cost.toFixed(1)}</span>` +
        `<span class="mark ${link.label}">${{ correct: "✓", wrong: "✗", unclear: "?" }[link.label] || ""}</span>`;
      li.addEventListener("click", () => selectLink(link, true));
      list.appendChild(li);
    }
  }
  function selectLink(link, play) {
    state.current = link;
    if (!state.segment || state.segment.segment_index !== link.segment_index) {
      $("filterSegment").checked = false;
      selectSegment(link.segment_index, false);
    }
    document.querySelectorAll("#linkList li").forEach((li) => li.classList.toggle("active", li.dataset.key === link.link_key));
    const active = document.querySelector("#linkList li.active");
    if (active) active.scrollIntoView({ block: "nearest" });
    renderCurrent();
    drawTimeline();
    replayLink(play);
  }
  function replayLink(play = true) {
    const link = state.current;
    if (!link) return;
    const lead = Math.round(0.8 * state.data.fps);
    seekFrame(Math.max(state.segment.first_frame, link.source_end_frame - lead), play);
  }
  function renderCurrent() {
    const link = state.current;
    const box = $("current");
    if (!link) { box.innerHTML = `<span class="detail">No link selected.</span>`; return; }
    box.innerHTML = `<div class="headline">` +
      `<strong style="color:${ballColor(link.ball_id)}">ball ${link.ball_id}</strong>` +
      `<span class="badge ${link.kind}">${link.kind}</span>` +
      `<span>${fmt(parseFloat(link.source_end_seconds))} (source time)</span>` +
      `<span class="detail">track ${link.source_track_id} ends @${link.source_end_frame}, track ${link.target_track_id} starts @${link.target_start_frame} · gap ${link.gap_frames} frames${link.hand ? " · hand " + link.hand.toLowerCase() : ""} · cost ${link.cost.toFixed(2)}${link.fit_rmse_px ? " · fit " + parseFloat(link.fit_rmse_px).toFixed(1) + " px" : ""}</span>` +
      `</div>` +
      `<div class="detail">Is the ball after the gap the same ball as before it?</div>` +
      `<textarea id="note" placeholder="note (optional): what actually happened">${link.note || ""}</textarea>` +
      `<div class="buttons">` +
      `<button class="good ${link.label === "correct" ? "on" : ""}" data-label="correct">c · correct</button>` +
      `<button class="bad ${link.label === "wrong" ? "on" : ""}" data-label="wrong">w · wrong</button>` +
      `<button class="meh ${link.label === "unclear" ? "on" : ""}" data-label="unclear">u · unclear</button>` +
      `<button id="replay">r · replay</button>` +
      `<span class="saved" id="savedAt"></span></div>`;
    box.querySelectorAll("button[data-label]").forEach((b) => b.addEventListener("click", () => saveLabel(b.dataset.label)));
    $("replay").addEventListener("click", () => replayLink(true));
  }
  async function saveLabel(label) {
    const link = state.current;
    if (!link) return;
    const note = $("note") ? $("note").value : "";
    const res = await fetch("/api/label", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ link_key: link.link_key, label, note }) });
    const body = await res.json();
    if (!res.ok) { alert(body.error || "save failed"); return; }
    link.label = label; link.note = note;
    state.data.label_counts = body.label_counts;
    updateStats();
    renderCurrent();
    $("savedAt").textContent = "saved";
    renderLinks();
    stepLink(1, false);
  }
  function stepLink(delta, play = true) {
    if (!state.links.length) return;
    const i = state.links.findIndex((l) => state.current && l.link_key === state.current.link_key);
    const next = state.links[Math.min(state.links.length - 1, Math.max(0, i + delta))];
    if (next && (!state.current || next.link_key !== state.current.link_key)) selectLink(next, play);
  }

  // --- header / table
  function updateStats() {
    const d = state.data;
    const segs = d.segments.filter((s) => s.video_offset !== null).length;
    const counts = Object.entries(d.link_counts).map(([k, v]) => `${v} ${k}`).join(" · ");
    const lc = d.label_counts;
    $("statSegments").textContent = `${segs} segments`;
    $("statLinks").textContent = `${d.links.length} links (${counts})`;
    $("statLabels").textContent = `labelled ${lc.correct + lc.wrong + lc.unclear}/${d.links.length} · ✓${lc.correct} ✗${lc.wrong} ?${lc.unclear}`;
  }
  function renderSegmentTable() {
    const rows = state.data.segments.map((s) => {
      const links = Object.entries(s.links || {}).map(([k, v]) => `${v} ${k}`).join(", ") || "–";
      return `<tr data-segment="${s.segment_index}"><td>seg ${s.segment_index} @ ${s.start_seconds.toFixed(1)}s</td>` +
        `<td>${s.ball_count} <span class="detail">(${s.ball_count_source})</span></td><td>${s.identities}</td><td>${s.tracklets}</td>` +
        `<td style="text-align:left">${links}</td><td>${s.unassigned_observed_frames}</td>` +
        `<td>${s.accel_y_px_per_frame2 ? s.accel_y_px_per_frame2.toFixed(2) : "–"}</td></tr>`;
    }).join("");
    $("segmentTable").innerHTML = `<tr><th>segment</th><th>balls</th><th>identities</th><th>tracklets</th><th style="text-align:left">links</th><th>unused frames</th><th>gravity</th></tr>${rows}`;
    $("segmentTable").querySelectorAll("tr[data-segment]").forEach((tr) => tr.addEventListener("click", () => selectSegment(parseInt(tr.dataset.segment, 10))));
  }
  function renderLegend() {
    $("legend").innerHTML = Object.entries(KIND_COLOR).map(([k, c]) => `<span><i style="background:${c}"></i>${k} link</span>`).join("") +
      `<span><i style="background:#2a2f36"></i>hidden</span>`;
  }

  // --- playback
  function setSpeed(speed) {
    state.speed = speed;
    video.playbackRate = speed;
    document.querySelectorAll("#speedGroup button").forEach((b) => b.classList.toggle("active", parseFloat(b.dataset.speed) === speed));
  }
  function tick() {
    const { seg, frame } = frameAtTime(video.currentTime);
    $("position").textContent = frame === null ? fmt(video.currentTime) :
      `frame ${frame} · ${fmt(frame / state.data.fps)} source · ${fmt(video.currentTime)} video`;
    if (seg && state.segment && seg.segment_index !== state.segment.segment_index && !video.paused) {
      selectSegment(seg.segment_index, false);
    }
    drawTimeline();
    if (!video.paused) state.raf = requestAnimationFrame(tick);
  }
  video.addEventListener("play", () => { cancelAnimationFrame(state.raf); state.raf = requestAnimationFrame(tick); });
  video.addEventListener("pause", tick);
  video.addEventListener("seeked", tick);

  document.querySelectorAll("#speedGroup button").forEach((b) => b.addEventListener("click", () => setSpeed(parseFloat(b.dataset.speed))));
  $("playPause").addEventListener("click", () => (video.paused ? video.play() : video.pause()));
  $("stepBack").addEventListener("click", () => { video.pause(); video.currentTime -= 1 / state.data.fps; });
  $("stepFwd").addEventListener("click", () => { video.pause(); video.currentTime += 1 / state.data.fps; });
  $("segmentSelect").addEventListener("change", (e) => selectSegment(parseInt(e.target.value, 10)));
  ["filterKind", "filterSegment", "filterUnlabelled"].forEach((id) => $(id).addEventListener("change", renderLinks));
  window.addEventListener("resize", drawTimeline);

  document.addEventListener("keydown", (e) => {
    if (e.target.tagName === "TEXTAREA" || e.target.tagName === "INPUT" || e.target.tagName === "SELECT") {
      if (e.key === "Escape") e.target.blur();
      return;
    }
    const keys = {
      " ": () => (video.paused ? video.play() : video.pause()),
      ArrowLeft: () => { video.currentTime -= 0.5; },
      ArrowRight: () => { video.currentTime += 0.5; },
      ",": () => { video.pause(); video.currentTime -= 1 / state.data.fps; },
      ".": () => { video.pause(); video.currentTime += 1 / state.data.fps; },
      j: () => stepLink(1), k: () => stepLink(-1), r: () => replayLink(true),
      c: () => saveLabel("correct"), w: () => saveLabel("wrong"), u: () => saveLabel("unclear"),
      "1": () => setSpeed(1), "2": () => setSpeed(0.5), "3": () => setSpeed(0.25),
    };
    if (keys[e.key]) { e.preventDefault(); keys[e.key](); }
  });

  async function boot() {
    const res = await fetch("/api/data");
    state.data = await res.json();
    $("videoName").textContent = state.data.video;
    const select = $("segmentSelect");
    for (const s of state.data.segments) {
      if (s.video_offset === null) continue;
      const opt = document.createElement("option");
      opt.value = String(s.segment_index);
      opt.textContent = `segment ${s.segment_index} · ${s.start_seconds.toFixed(1)}s · ${s.ball_count} balls`;
      select.appendChild(opt);
    }
    updateStats();
    renderSegmentTable();
    renderLegend();
    const first = state.data.segments.find((s) => s.video_offset !== null);
    if (first) selectSegment(first.segment_index, false);
    if (state.links.length) selectLink(state.links[0], false);
    tick();
  }
  boot();
})();
