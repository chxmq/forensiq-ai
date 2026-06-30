"""Runtime policy configuration — weights and decision thresholds.

Values persist to ``storage/policy.json`` so underwriters can tune escalation
rules from the UI without redeploying.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.core.config import settings

POLICY_PATH = settings.storage_dir / "policy.json"

POLICY_FIELDS = (
    "weight_document",
    "weight_financial",
    "weight_verification",
    "weight_gis",
    "weight_intake",
    "threshold_approve",
    "threshold_review",
    "threshold_escalate",
)


def _snapshot() -> dict[str, Any]:
    return {
        "weights": {
            "document": settings.weight_document,
            "financial": settings.weight_financial,
            "verification": settings.weight_verification,
            "gis": settings.weight_gis,
            "intake": settings.weight_intake,
        },
        "thresholds": {
            "approve": settings.threshold_approve,
            "review": settings.threshold_review,
            "escalate": settings.threshold_escalate,
        },
    }


def load_persisted() -> None:
    """Apply saved overrides on startup."""
    if not POLICY_PATH.exists():
        return
    try:
        data = json.loads(POLICY_PATH.read_text())
        for key in POLICY_FIELDS:
            if key in data:
                setattr(settings, key, data[key])
    except (json.JSONDecodeError, TypeError, ValueError):
        pass


def read_policy() -> dict[str, Any]:
    return _snapshot()


def update_policy(payload: dict[str, Any]) -> dict[str, Any]:
    flat: dict[str, float] = {}
    if "weights" in payload and isinstance(payload["weights"], dict):
        w = payload["weights"]
        mapping = {
            "document": "weight_document",
            "financial": "weight_financial",
            "verification": "weight_verification",
            "gis": "weight_gis",
            "intake": "weight_intake",
        }
        for src, dst in mapping.items():
            if src in w:
                flat[dst] = float(w[src])
    if "thresholds" in payload and isinstance(payload["thresholds"], dict):
        t = payload["thresholds"]
        mapping = {
            "approve": "threshold_approve",
            "review": "threshold_review",
            "escalate": "threshold_escalate",
        }
        for src, dst in mapping.items():
            if src in t:
                flat[dst] = float(t[src])

    for key, value in flat.items():
        setattr(settings, key, value)

    existing = {}
    if POLICY_PATH.exists():
        try:
            existing = json.loads(POLICY_PATH.read_text())
        except json.JSONDecodeError:
            existing = {}
    existing.update(flat)
    POLICY_PATH.parent.mkdir(parents=True, exist_ok=True)
    POLICY_PATH.write_text(json.dumps(existing, indent=2))
    return _snapshot()
