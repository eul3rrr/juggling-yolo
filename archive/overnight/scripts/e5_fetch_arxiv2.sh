#!/usr/bin/env bash
# Second batch of arXiv searches for E5 (more targeted).
set -u
BASE="/home/it-admin/.hermes/profiles/juggling-tracker/workspace/juggling-yolo/experiments/overnight"
RAW="$BASE/data/e5_raw"
PY="/home/it-admin/.hermes/profiles/juggling-tracker/workspace/juggling-yolo/.venv/bin/python"

fetch() {
  local slug="$1"; shift
  local query="$1"; shift
  echo "=== $slug ==="
  curl -s --max-time 60 "https://export.arxiv.org/api/query?search_query=${query}&max_results=10&sortBy=relevance" \
    | "$PY" "$BASE/scripts/e5_parse_arxiv.py" > "$RAW/${slug}.txt" 2>&1
  head -2 "$RAW/${slug}.txt"
  sleep 3
}

fetch juggling "all:juggling+AND+cat:cs.CV"
fetch juggling2 "all:%22juggling%22+AND+all:robot"
fetch ballistic-video "all:ballistic+AND+all:trajectory+AND+cat:cs.CV"
fetch physics-prior-tracking "all:%22physics-informed%22+AND+all:tracking"
fetch heatmap-small "all:%22heat+map%22+AND+all:%22small+object%22+AND+all:detection+AND+cat:cs.CV"
fetch gravity-monocular "all:gravity+AND+all:monocular+AND+all:trajectory"
fetch interp-occlusion "all:%22trajectory+interpolation%22+AND+all:tracking"
fetch spt-microscopy "all:%22single-particle+tracking%22+AND+all:%22motion+model%22"
echo DONE
