"""
app/services/deal_registry_service.py

In-memory deal registry.

Keeps a lightweight record of every deal that has been created via
POST /deals.  Optionally stores the last pipeline result so GET /deals/{id}
can return a deal's current analytical state without re-running the pipeline.

This is a Phase 1 in-process store — data lives for the lifetime of the
server process.  Phase 2+: replace with a persistent store (PostgreSQL,
DynamoDB, etc.) via a registry-store-mcp connector.

Thread safety: all mutations are protected by a threading.Lock so the
registry is safe for use with uvicorn's default single-process async loop
and for concurrent pytest runs that share the same interpreter.
"""

import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Registry store
# ---------------------------------------------------------------------------

_lock: threading.Lock = threading.Lock()

# deal_id → _DealRecord dict
_registry: Dict[str, Dict[str, Any]] = {}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def register(deal_input: Dict[str, Any]) -> Dict[str, Any]:
    """
    Register a new deal (or update an existing one).

    Parameters
    ----------
    deal_input : The deal input dict (validated before calling this).

    Returns
    -------
    The stored deal record.
    """
    deal_id = deal_input.get("deal_id", "unknown")
    record = _make_record(deal_input)
    with _lock:
        _registry[deal_id] = record
    return record


def get(deal_id: str) -> Optional[Dict[str, Any]]:
    """Return the deal record for deal_id, or None if not found."""
    with _lock:
        return _registry.get(deal_id)


def list_all() -> List[Dict[str, Any]]:
    """Return a list of all deal records, sorted by registered_at descending."""
    with _lock:
        records = list(_registry.values())
    records.sort(key=lambda r: r.get("registered_at", ""), reverse=True)
    return records


def update_pipeline_result(deal_id: str, pipeline_result: Dict[str, Any]) -> bool:
    """
    Attach the latest pipeline result to an existing deal record.

    Returns True if the deal was found and updated, False otherwise.
    """
    with _lock:
        if deal_id not in _registry:
            return False
        _registry[deal_id]["last_pipeline_result"] = pipeline_result
        _registry[deal_id]["last_pipeline_at"] = datetime.now(timezone.utc).isoformat()
        _registry[deal_id]["pipeline_count"] = (
            _registry[deal_id].get("pipeline_count", 0) + 1
        )
    return True


def unregister(deal_id: str) -> bool:
    """Remove a deal from the registry.  Returns True if it existed."""
    with _lock:
        if deal_id in _registry:
            del _registry[deal_id]
            return True
    return False


def clear() -> int:
    """Clear all records.  Returns the number of records removed."""
    with _lock:
        n = len(_registry)
        _registry.clear()
    return n


def count() -> int:
    """Return the number of registered deals."""
    with _lock:
        return len(_registry)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _make_record(deal_input: Dict[str, Any]) -> Dict[str, Any]:
    coll = deal_input.get("collateral", {})
    liabilities = deal_input.get("liabilities", [])
    return {
        "deal_id":            deal_input.get("deal_id", "unknown"),
        "name":               deal_input.get("name", ""),
        "issuer":             deal_input.get("issuer", ""),
        "region":             deal_input.get("region"),
        "currency":           deal_input.get("currency", "USD"),
        "manager":            deal_input.get("manager"),
        "registered_at":      datetime.now(timezone.utc).isoformat(),
        "status":             "active",
        "portfolio_size":     coll.get("portfolio_size"),
        "asset_class":        coll.get("asset_class"),
        "tranche_count":      len(liabilities),
        "pipeline_count":     0,
        "last_pipeline_at":   None,
        "last_pipeline_result": None,
        # Keep a copy of the full deal_input for re-running workflows
        "deal_input":         deal_input,
    }
