"""
app/services/watchlist_service.py

In-memory watchlist for deal metric threshold alerts.

A watchlist item defines a threshold condition on a single output metric.
When a deal's latest base-case outputs are checked against the watchlist,
any item whose condition is breached produces an "alert" entry.

Supported operators: lt (less than), lte, gt, gte, eq

Example:
    add_item(
        metric="equity_irr",
        operator="lt",
        threshold=0.08,
        label="IRR < 8% warning",
        deal_id="deal-001",        # optional: only triggers for this deal
    )

Phase 1: in-process store.
Phase 2+: persist to a database via watchlist-store-mcp.

Thread safety: protected by threading.Lock.
"""

import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------

_lock: threading.Lock = threading.Lock()
_items: Dict[str, Dict[str, Any]] = {}

VALID_OPERATORS = ("lt", "lte", "gt", "gte", "eq")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def add_item(
    metric: str,
    operator: str,
    threshold: float,
    label: Optional[str] = None,
    deal_id: Optional[str] = None,
    severity: str = "warning",
) -> Dict[str, Any]:
    """
    Add a watchlist item.

    Parameters
    ----------
    metric     : Output metric name (e.g. "equity_irr", "oc_cushion_aaa").
    operator   : Comparison operator: lt, lte, gt, gte, eq.
    threshold  : Numeric threshold value.
    label      : Human-readable description.
    deal_id    : If set, the item only applies to this specific deal.
                 If None, applies to all deals.
    severity   : "warning" or "critical".

    Returns
    -------
    The stored watchlist item dict.
    """
    if operator not in VALID_OPERATORS:
        raise ValueError(f"Invalid operator '{operator}'. Must be one of {VALID_OPERATORS}.")

    item_id = f"wl-{uuid.uuid4().hex[:8]}"
    item = {
        "item_id":    item_id,
        "metric":     metric,
        "operator":   operator,
        "threshold":  threshold,
        "label":      label or f"{metric} {operator} {threshold}",
        "deal_id":    deal_id,
        "severity":   severity,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "active":     True,
    }
    with _lock:
        _items[item_id] = item
    return item


def get_item(item_id: str) -> Optional[Dict[str, Any]]:
    """Return a watchlist item by ID, or None if not found."""
    with _lock:
        return _items.get(item_id)


def list_items(deal_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Return all active watchlist items, optionally filtered to a specific deal.

    Items with deal_id=None apply to all deals and are always included.
    Items with a specific deal_id are included only when filter matches.
    """
    with _lock:
        items = list(_items.values())
    active = [i for i in items if i.get("active", True)]
    if deal_id is not None:
        active = [i for i in active if i["deal_id"] is None or i["deal_id"] == deal_id]
    active.sort(key=lambda i: i["created_at"])
    return active


def remove_item(item_id: str) -> bool:
    """Remove a watchlist item. Returns True if it existed."""
    with _lock:
        if item_id in _items:
            del _items[item_id]
            return True
    return False


def deactivate_item(item_id: str) -> bool:
    """Soft-disable a watchlist item (keeps it in the store). Returns True if found."""
    with _lock:
        if item_id in _items:
            _items[item_id]["active"] = False
            return True
    return False


def clear() -> int:
    """Remove all items. Returns the number removed."""
    with _lock:
        n = len(_items)
        _items.clear()
    return n


def count() -> int:
    """Return total number of stored items (active and inactive)."""
    with _lock:
        return len(_items)


# ---------------------------------------------------------------------------
# Check logic
# ---------------------------------------------------------------------------

def check_outputs(
    outputs: Dict[str, Any],
    deal_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Evaluate all applicable watchlist items against a set of outputs.

    Returns a list of alert dicts for every item whose condition is breached.
    Items not applicable to this deal_id are skipped.
    Items whose metric is not present in outputs are skipped.
    """
    applicable = list_items(deal_id=deal_id)
    alerts: List[Dict[str, Any]] = []

    for item in applicable:
        metric = item["metric"]
        value = outputs.get(metric)
        if value is None:
            continue

        threshold = item["threshold"]
        op = item["operator"]
        triggered = _evaluate(value, op, threshold)

        alerts.append({
            "item_id":   item["item_id"],
            "label":     item["label"],
            "metric":    metric,
            "operator":  op,
            "threshold": threshold,
            "value":     value,
            "triggered": triggered,
            "severity":  item["severity"],
        })

    return alerts


def _evaluate(value: float, operator: str, threshold: float) -> bool:
    if operator == "lt":
        return value < threshold
    if operator == "lte":
        return value <= threshold
    if operator == "gt":
        return value > threshold
    if operator == "gte":
        return value >= threshold
    if operator == "eq":
        return value == threshold
    return False
