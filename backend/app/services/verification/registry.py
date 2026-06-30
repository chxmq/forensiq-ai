"""Access layer for the (mock) trusted external registries.

In production these would be live API integrations with land-record systems,
CERSAI/encumbrance databases and identity/tax authorities. Here they are local
JSON snapshots with identical lookup semantics, so the verification logic is
exactly what would run against the real sources.
"""
from __future__ import annotations

import json
from difflib import SequenceMatcher
from functools import lru_cache
from typing import Any

from app.core.config import settings

REG_DIR = settings.data_dir / "registries"


@lru_cache
def _load(name: str) -> dict[str, Any]:
    path = REG_DIR / name
    if not path.exists():
        return {"records": []}
    return json.loads(path.read_text())


def name_similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


def find_land_record(survey_number: str | None, address: str | None) -> dict[str, Any] | None:
    records = _load("land_registry.json")["records"]
    if survey_number:
        sn = survey_number.replace(" ", "").lower()
        for r in records:
            if r["survey_number"].replace(" ", "").lower() == sn:
                return r
    if address:
        best, score = None, 0.0
        for r in records:
            s = name_similarity(address, r.get("address", ""))
            if s > score:
                best, score = r, s
        if score >= 0.45:
            return best
    return None


def find_identity(pan: str | None, name: str | None) -> dict[str, Any] | None:
    records = _load("identity_registry.json")["records"]
    if pan:
        for r in records:
            if r["pan"].upper() == pan.upper():
                return r
    if name:
        best, score = None, 0.0
        for r in records:
            s = name_similarity(name, r.get("name", ""))
            if s > score:
                best, score = r, s
        if score >= 0.6:
            return best
    return None
