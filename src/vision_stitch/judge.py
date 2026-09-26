"""OpenRouter judge client, verdict parsing, and a resumable batch runner."""
from __future__ import annotations

import csv
import json
import os
import re
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

DEFAULT_MODEL = "deepseek/deepseek-v4.1-flash"
DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
VALID_DECISIONS = ("stitch", "none", "uncertain")
RESULT_FIELDS = ["event_key", "model", "prompt_version", "reasoning_effort", "decision", "candidate_letter",
                 "candidate_track_id", "confidence", "reason", "parse_ok", "latency_s",
                 "prompt_tokens", "completion_tokens", "reasoning_tokens", "cost_usd",
                 "judged_at", "error"]


@dataclass(frozen=True)
class JudgeConfig:
    model: str = DEFAULT_MODEL
    base_url: str = DEFAULT_BASE_URL
    timeout: int = 900
    # This model is a heavy reasoner: with ~15 images it can spend well over 6000
    # tokens thinking and return nothing at all if the budget runs out.  The budget
    # is only charged for tokens actually produced, so a generous cap is cheap.
    max_tokens: int = 16000
    reasoning_effort: str = "low"
    # Some events make the model think past any sane budget and return nothing.
    # Those get one more attempt with the cheapest thinking level, which reliably
    # finishes.  Capping reasoning tokens instead does not work on this model.
    fallback_reasoning_effort: str = "minimal"
    temperature: float = 0.0
    retries: int = 3
    retry_delay: float = 5.0

    def efforts(self) -> list[str]:
        return [self.reasoning_effort] if self.fallback_reasoning_effort in (None, "", self.reasoning_effort) \
            else [self.reasoning_effort, self.fallback_reasoning_effort]

    def as_dict(self) -> dict:
        return asdict(self)


def resolve_api_key(explicit: str | None = None) -> str:
    """OpenRouter key from explicit value, environment, or the Hermes profile store."""
    if explicit:
        return explicit
    from_env = os.environ.get("OPENROUTER_API_KEY")
    if from_env:
        return from_env
    candidates = [Path.home() / ".hermes" / "profiles" / "juggling-tracker" / "auth.json",
                  Path.home() / ".hermes" / "auth.json"]
    for path in candidates:
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text())
        except (OSError, ValueError):
            continue
        for entry in data.get("credential_pool", {}).get("openrouter", []):
            token = entry.get("access_token")
            if token:
                return token
    raise RuntimeError("No OpenRouter API key found (set OPENROUTER_API_KEY or store one with `hermes auth`)")


def event_slug(event_key: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", event_key)


def extract_json(text: str | None) -> dict | None:
    """Tolerant JSON object extraction (handles code fences and surrounding prose)."""
    if not text:
        return None
    cleaned = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", cleaned, re.S)
    if fence:
        cleaned = fence.group(1).strip()
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        parsed = json.loads(cleaned[start:end + 1])
    except ValueError:
        return None
    return parsed if isinstance(parsed, dict) else None


def parse_verdict(text: str | None, letters: list[str]) -> dict:
    """Normalise a model answer into a verdict record; never raises."""
    if not text:
        return dict(parse_ok=False, decision=None, candidate_letter=None, confidence=None, reason=None,
                    error="empty answer (open-ended reasoning most likely exhausted max_tokens)")
    payload = extract_json(text)
    if payload is None:
        return dict(parse_ok=False, decision=None, candidate_letter=None, confidence=None,
                    reason=None, error="no JSON object in answer")
    decision = str(payload.get("decision", "")).strip().lower()
    candidate = payload.get("candidate")
    candidate_letter = str(candidate).strip().upper() if isinstance(candidate, str) and candidate.strip() else None
    confidence = payload.get("confidence")
    try:
        confidence = float(confidence) if confidence is not None else None
    except (TypeError, ValueError):
        confidence = None
    if confidence is not None:
        confidence = min(1.0, max(0.0, confidence))
    reason = payload.get("reason")
    reason = str(reason).strip()[:400] if reason is not None else None
    error = None
    if decision not in VALID_DECISIONS:
        error = f"invalid decision {decision!r}"
    elif candidate_letter is not None and candidate_letter not in letters:
        error = f"candidate {candidate_letter!r} not offered"
    elif decision == "stitch" and candidate_letter is None:
        error = "decision 'stitch' without a candidate"
    elif decision != "stitch":
        candidate_letter = None
    return dict(parse_ok=error is None, decision=decision, candidate_letter=candidate_letter,
                confidence=confidence, reason=reason, error=error)


class JudgeLike(Protocol):
    """Anything that can answer one event (the real client, or a test double)."""

    def judge(self, content: list[dict], letters: list[str]) -> dict: ...


class JudgeClient:
    """Minimal OpenRouter chat-completions client for one vision judgement."""

    def __init__(self, config: JudgeConfig, api_key: str):
        self.config = config
        self.api_key = api_key

    def judge(self, content: list[dict], letters: list[str]) -> dict:
        last: dict = {}
        for effort in self.config.efforts():
            last = self._attempt(content, letters, effort)
            if last["verdict"].get("parse_ok") or last.get("error"):
                return last
        return last

    def _attempt(self, content: list[dict], letters: list[str], effort: str | None) -> dict:
        payload = {
            "model": self.config.model,
            "messages": [{"role": "user", "content": content}],
            "max_tokens": self.config.max_tokens,
            "temperature": self.config.temperature,
        }
        if effort:
            payload["reasoning"] = {"effort": effort}
        request = urllib.request.Request(
            f"{self.config.base_url.rstrip('/')}/chat/completions",
            data=json.dumps(payload).encode(),
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"})
        started = time.time()
        last_error = None
        for attempt in range(1, self.config.retries + 1):
            try:
                body = unquote_secrets(urllib.request.urlopen(request, timeout=self.config.timeout).read())
                response = json.loads(body)
                message = response["choices"][0]["message"]
                usage = response.get("usage", {}) or {}
                details = usage.get("completion_tokens_details", {}) or {}
                verdict = parse_verdict(message.get("content"), letters)
                return dict(
                    raw_text=message.get("content"), verdict=verdict, reasoning_effort=effort,
                    usage=dict(prompt_tokens=usage.get("prompt_tokens"), completion_tokens=usage.get("completion_tokens"),
                               reasoning_tokens=details.get("reasoning_tokens"), cost_usd=usage.get("cost")),
                    latency_s=round(time.time() - started, 2), error=None,
                )
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode(errors="replace")[:400]
                last_error = f"HTTP {exc.code}: {detail}"
                if exc.code in (400, 401, 403, 404):
                    break
            except (urllib.error.URLError, TimeoutError, ValueError, KeyError) as exc:
                last_error = f"{type(exc).__name__}: {exc}"
            if attempt < self.config.retries:
                time.sleep(self.config.retry_delay * attempt)
        return dict(raw_text=None, reasoning_effort=effort,
                    verdict=dict(parse_ok=False, decision=None, candidate_letter=None,
                                 confidence=None, reason=None, error=last_error),
                    usage={}, latency_s=round(time.time() - started, 2), error=last_error)


def unquote_secrets(body: bytes) -> bytes:
    """Placeholder hook for response sanitising; identity by default."""
    return body


def load_manifests(events_root: Path) -> list[dict]:
    manifests = []
    for path in sorted(Path(events_root).glob("*/manifest.json")):
        manifests.append(json.loads(path.read_text()))
    return manifests


def result_is_current(result: dict, manifest: dict, config: JudgeConfig) -> bool:
    return (result.get("model") == config.model
            and result.get("prompt_version") == manifest.get("prompt_version")
            and result.get("verdict", {}).get("parse_ok") is True)


def run_judge(events_root: Path, results_root: Path, client: JudgeLike, config: JudgeConfig,
              concurrency: int = 6, limit: int | None = None, only: list[str] | None = None,
              force: bool = False) -> dict:
    """Judge every event manifest under ``events_root``; resumable per event."""
    from src.vision_stitch.prompt import build_request

    events_root, results_root = Path(events_root), Path(results_root)
    results_root.mkdir(parents=True, exist_ok=True)
    manifests = load_manifests(events_root)
    if only:
        wanted = set(only)
        manifests = [m for m in manifests if m["event_key"] in wanted or event_slug(m["event_key"]) in wanted]
    pending = []
    skipped = 0
    for manifest in manifests:
        target = results_root / f"{event_slug(manifest['event_key'])}.json"
        if target.is_file() and not force:
            try:
                existing = json.loads(target.read_text())
            except ValueError:
                existing = {}
            if result_is_current(existing, manifest, config):
                skipped += 1
                continue
        pending.append(manifest)
    if limit is not None:
        pending = pending[:limit]

    stats = dict(manifests=len(manifests), skipped_current=skipped, judged=0, parse_failures=0,
                 errors=0, cost_usd=0.0, total_latency_s=0.0)

    def judge_one(manifest: dict) -> dict:
        content = build_request(manifest, events_root / event_slug(manifest["event_key"]))
        letters = [c["letter"] for c in manifest["candidates"]]
        outcome = client.judge(content, letters)
        record = dict(
            event_key=manifest["event_key"], model=config.model,
            prompt_version=manifest.get("prompt_version"),
            judged_at=datetime.now(timezone.utc).isoformat(),
            **outcome,
        )
        record["candidate_track_id"] = next(
            (c["track_id"] for c in manifest["candidates"]
             if c["letter"] == outcome["verdict"].get("candidate_letter")), None)
        return record

    with ThreadPoolExecutor(max_workers=max(1, concurrency)) as pool:
        futures = {pool.submit(judge_one, m): m for m in pending}
        for future in as_completed(futures):
            record = future.result()
            (results_root / f"{event_slug(record['event_key'])}.json").write_text(
                json.dumps(record, indent=2, sort_keys=True) + "\n")
            stats["judged"] += 1
            if not record["verdict"].get("parse_ok"):
                stats["parse_failures"] += 1
            if record.get("error"):
                stats["errors"] += 1
            stats["cost_usd"] += float(record["usage"].get("cost_usd") or 0.0)
            stats["total_latency_s"] += record.get("latency_s") or 0.0
            write_results_csv(results_root, manifests)
    write_results_csv(results_root, manifests)
    stats["cost_usd"] = round(stats["cost_usd"], 4)
    return stats


def write_results_csv(results_root: Path, manifests: list[dict]) -> Path:
    """Rewrite the flat results table from the per-event JSON files."""
    manifest_by_key = {m["event_key"]: m for m in manifests}
    rows = []
    for path in sorted(Path(results_root).glob("*.json")):
        try:
            record = json.loads(path.read_text())
        except ValueError:
            continue
        if "event_key" not in record:
            continue
        manifest = manifest_by_key.get(record["event_key"], {})
        verdict = record.get("verdict", {})
        usage = record.get("usage", {})
        rows.append({
            "event_key": record["event_key"], "model": record.get("model"),
            "prompt_version": record.get("prompt_version"),
            "reasoning_effort": record.get("reasoning_effort"),
            "decision": verdict.get("decision"), "candidate_letter": verdict.get("candidate_letter"),
            "candidate_track_id": record.get("candidate_track_id"),
            "confidence": verdict.get("confidence"), "reason": verdict.get("reason"),
            "parse_ok": verdict.get("parse_ok"), "latency_s": record.get("latency_s"),
            "prompt_tokens": usage.get("prompt_tokens"), "completion_tokens": usage.get("completion_tokens"),
            "reasoning_tokens": usage.get("reasoning_tokens"), "cost_usd": usage.get("cost_usd"),
            "judged_at": record.get("judged_at"), "error": record.get("error") or verdict.get("error"),
        })
    rows.sort(key=lambda r: (r["event_key"] or ""))
    target = Path(results_root) / "results.csv"
    with target.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=RESULT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return target
