"""
Passive observability helpers for agent runs.

This module is intentionally local-file based for the MVP. It must never
interrupt the chat flow if trace persistence fails.
"""

import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from app.config import (
    OBSERVABILITY_DIR,
    OBSERVABILITY_ENABLED,
    OBSERVABILITY_LOG_PROMPTS,
)


RUN_FIELDS = [
    "timestamp",
    "tenant_id",
    "session_id",
    "user_message",
    "model",
    "generation_id",
    "latency_ms",
    "prompt_tokens",
    "completion_tokens",
    "total_tokens",
    "cost",
    "prompt_chars",
    "response_chars",
    "next_action",
    "confidence",
    "context_policy",
    "catalog_mode",
    "include_brand",
    "include_dealers",
    "error",
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _observability_dir() -> Path:
    return Path(OBSERVABILITY_DIR)


def _runs_file() -> Path:
    return _observability_dir() / "agent_runs.jsonl"


def _prompts_dir() -> Path:
    return _observability_dir() / "prompts"


def _safe_filename(value: Any) -> str:
    text = str(value or "session").strip()
    text = re.sub(r"[^A-Za-z0-9_.-]+", "_", text)
    return text[:120] or "session"


def _to_number(value: Any) -> Optional[float]:
    if value is None:
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _average(values: list[float]) -> float:
    if not values:
        return 0

    return round(sum(values) / len(values), 2)


def build_agent_run_trace(
    *,
    tenant_id: str,
    session_id: str,
    user_message: str,
    model: str,
    prompt: str,
    assistant_reply: str,
    result: Dict[str, Any],
    context_policy: Optional[Dict[str, Any]] = None,
    generation_id: Optional[str] = None,
    latency_ms: Optional[float] = None,
    prompt_tokens: Optional[int] = None,
    completion_tokens: Optional[int] = None,
    total_tokens: Optional[int] = None,
    cost: Optional[float] = None,
    error: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Build a minimal trace from already available runtime data.

    Provider metadata remains optional so LLM interfaces do not need to change.
    """
    policy = context_policy or {}

    return {
        "timestamp": _now_iso(),
        "tenant_id": tenant_id,
        "session_id": session_id,
        "user_message": user_message,
        "model": model,
        "generation_id": generation_id,
        "latency_ms": latency_ms,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "cost": cost,
        "prompt_chars": len(prompt or ""),
        "response_chars": len(assistant_reply or ""),
        "next_action": result.get("next_action"),
        "confidence": result.get("confidence"),
        "context_policy": policy or None,
        "catalog_mode": policy.get("catalog_mode"),
        "include_brand": policy.get("include_brand"),
        "include_dealers": policy.get("include_dealers"),
        "error": error,
    }


def record_agent_run(
    *,
    trace: Dict[str, Any],
    prompt: Optional[str] = None,
) -> None:
    """
    Append one agent run trace to JSONL.

    This function is deliberately defensive: observability is passive and must
    never break the user-facing response.
    """
    if not OBSERVABILITY_ENABLED:
        return

    try:
        observability_dir = _observability_dir()
        observability_dir.mkdir(parents=True, exist_ok=True)

        normalized_trace = {
            field: trace.get(field)
            for field in RUN_FIELDS
        }

        if not normalized_trace.get("timestamp"):
            normalized_trace["timestamp"] = _now_iso()

        with _runs_file().open("a", encoding="utf-8") as file:
            file.write(json.dumps(normalized_trace, ensure_ascii=False, default=str))
            file.write("\n")

        if OBSERVABILITY_LOG_PROMPTS and prompt:
            prompts_dir = _prompts_dir()
            prompts_dir.mkdir(parents=True, exist_ok=True)

            session_id = _safe_filename(normalized_trace.get("session_id"))
            timestamp = _safe_filename(normalized_trace.get("timestamp"))
            prompt_path = prompts_dir / f"{session_id}_{timestamp}.txt"
            prompt_path.write_text(prompt, encoding="utf-8")

    except Exception as exc:
        print(f"[OBSERVABILITY] Error saving agent run trace: {exc}")


def get_observability_summary() -> Dict[str, Any]:
    """
    Return a lightweight aggregate summary from the local JSONL trace file.
    """
    summary = {
        "total_runs": 0,
        "average_latency_ms": 0,
        "average_total_tokens": 0,
        "total_cost": 0,
        "runs_by_next_action": {},
        "runs_by_tenant": {},
    }

    runs_file = _runs_file()

    if not runs_file.exists():
        return summary

    latencies = []
    total_tokens = []
    cost_sum = 0.0
    runs_by_next_action = Counter()
    runs_by_tenant = Counter()

    try:
        with runs_file.open("r", encoding="utf-8") as file:
            for line in file:
                line = line.strip()

                if not line:
                    continue

                try:
                    run = json.loads(line)
                except json.JSONDecodeError:
                    continue

                summary["total_runs"] += 1

                latency = _to_number(run.get("latency_ms"))
                if latency is not None:
                    latencies.append(latency)

                tokens = _to_number(run.get("total_tokens"))
                if tokens is not None:
                    total_tokens.append(tokens)

                cost = _to_number(run.get("cost"))
                if cost is not None:
                    cost_sum += cost

                runs_by_next_action[run.get("next_action") or "unknown"] += 1
                runs_by_tenant[run.get("tenant_id") or "unknown"] += 1

    except Exception as exc:
        print(f"[OBSERVABILITY] Error reading observability summary: {exc}")
        return summary

    summary["average_latency_ms"] = _average(latencies)
    summary["average_total_tokens"] = _average(total_tokens)
    summary["total_cost"] = round(cost_sum, 6)
    summary["runs_by_next_action"] = dict(runs_by_next_action)
    summary["runs_by_tenant"] = dict(runs_by_tenant)

    return summary
