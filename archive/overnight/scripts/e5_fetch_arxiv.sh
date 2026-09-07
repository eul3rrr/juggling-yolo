#!/usr/bin/env bash
# Batched arXiv metadata search for the overnight literature sweep (E5).
# Writes raw parsed results into experiments/overnight/data/e5_raw/<slug>.txt

set -u
BASE="/home/it-admin/.hermes/profiles/juggling-tracker/workspace/juggling-yolo/experiments/overnight"
RAW="$BASE/data/e5_raw"
mkdir -p "$RAW"

PY="/home/it-admin/.hermes/profiles/juggling-tracker/workspace/juggling-yolo/.venv/bin/python"

fetch() {
  local slug="$1"; shift
  local query="$1"; shift
  local extra="${1:-}"
  echo "=== $slug ==="
  curl -s --max-time 60 "https://export.arxiv.org/api/query?search_query=${query}&max_results=12&sortBy=relevance${extra}" \
    | "$PY" "$BASE/scripts/e5_parse_arxiv.py" > "$RAW/${slug}.txt" 2>&1
  head -3 "$RAW/${slug}.txt"
  sleep 3
}

fetch ball-sports "all:%22ball+tracking%22+AND+cat:cs.CV"
fetch tracknet "all:TrackNet"
fetch physics-mot "all:%22multi-object+tracking%22+AND+all:%22motion+model%22+AND+all:occlusion"
fetch mincostflow "all:%22multi-object+tracking%22+AND+all:%22minimum+cost+flow%22"
fetch trajectory-stitch "all:%22tracklet%22+AND+all:stitching+AND+cat:cs.CV"
fetch mot-survey "all:%22multiple+object+tracking%22+AND+all:survey"
fetch kalman-small "all:Kalman+AND+all:%22small+object%22+AND+all:tracking"
fetch pmbs-filter "all:%22Poisson+multi-Bernoulli%22+AND+all:tracking"
fetch gnn-tracking "all:%22graph+neural+network%22+AND+all:%22multi-object+tracking%22"
fetch offline-mot "all:%22offline%22+AND+all:%22multi-object+tracking%22+AND+all:global"
echo DONE
