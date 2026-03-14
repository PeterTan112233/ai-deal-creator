"""
Audit logger for AI Deal Creator.

Every workflow action must emit an audit event.
Events are written as newline-delimited JSON to the audit log file.
"""

import json
import os
from datetime import datetime
from typing import Any, Dict, Optional

_LOG_PATH = os.environ.get("AUDIT_LOG_PATH", "data/audit_log.jsonl")


def record_event(
    event_type: str,
    deal_id: str,
    payload: Dict[str, Any],
    actor: Optional[str] = None,
    scenario_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Write a structured audit event to the audit log.

    event_type examples:
      deal.created | scenario.submitted | scenario.completed |
      comparison.run | draft.generated | approval.requested |
      approval.granted | artifact.published
    """
    event = {
        "event_id": _new_event_id(),
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "event_type": event_type,
        "deal_id": deal_id,
        "scenario_id": scenario_id,
        "actor": actor or "system",
        "payload": payload,
    }

    _append(event)
    return event


def get_all_events(
    limit: int = 200,
    offset: int = 0,
    deal_id: Optional[str] = None,
    event_type: Optional[str] = None,
) -> Dict[str, Any]:
    """Return all audit events with optional filtering and pagination."""
    all_events = []
    if os.path.exists(_LOG_PATH):
        with open(_LOG_PATH) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                    if deal_id and event.get("deal_id") != deal_id:
                        continue
                    if event_type and event.get("event_type") != event_type:
                        continue
                    all_events.append(event)
                except json.JSONDecodeError:
                    continue

    # Newest first
    all_events.reverse()
    total = len(all_events)
    page = all_events[offset : offset + limit]
    return {"total": total, "offset": offset, "limit": limit, "events": page}


def get_event_history(deal_id: str) -> list:
    """
    Return all audit events for a given deal_id from the log file.
    """
    events = []
    if not os.path.exists(_LOG_PATH):
        return events

    with open(_LOG_PATH) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
                if event.get("deal_id") == deal_id:
                    events.append(event)
            except json.JSONDecodeError:
                continue

    return events


def _append(event: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(_LOG_PATH), exist_ok=True)
    with open(_LOG_PATH, "a") as f:
        f.write(json.dumps(event) + "\n")


def _new_event_id() -> str:
    import uuid
    return f"evt-{uuid.uuid4().hex[:12]}"
