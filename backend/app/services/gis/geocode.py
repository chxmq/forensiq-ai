"""Offline property location resolution for bank underwriting.

Bank staff enter a property address and upload land title documents — they do
not supply GPS coordinates. This module resolves lat/lng automatically from:

1. Land registry match (survey number from OCR or address fuzzy match)
2. Pincode in the typed address
3. Locality / city keywords in the address

In production this would call an internal geocoder or Bhuvan / NIC GIS service;
for the hackathon demo we use bundled registry + pincode data (fully offline).
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from typing import Any

from app.core.config import settings
from app.services.verification import registry

PINCODE_RE = re.compile(r"\b(\d{6})\b")


@lru_cache
def _pincode_data() -> dict[str, Any]:
    path = settings.data_dir / "registries" / "pincode_centroids.json"
    if not path.exists():
        return {"records": [], "locality_aliases": []}
    return json.loads(path.read_text())


def _from_pincode(address: str) -> dict[str, Any] | None:
    if not address:
        return None
    pincodes = {r["pincode"]: r for r in _pincode_data().get("records", [])}
    for match in PINCODE_RE.findall(address):
        if match in pincodes:
            row = pincodes[match]
            return {
                "lat": row["lat"],
                "lng": row["lng"],
                "source": "pincode",
                "source_label": f"Pincode {match} ({row['locality']})",
                "confidence": 0.72,
            }
    addr = address.lower()
    for alias in _pincode_data().get("locality_aliases", []):
        if any(kw in addr for kw in alias["keywords"]):
            return {
                "lat": alias["lat"],
                "lng": alias["lng"],
                "source": "locality",
                "source_label": f"Address locality ({alias['label']})",
                "confidence": 0.6,
            }
    return None


def resolve_property_location(
    property_address: str | None,
    survey_number: str | None = None,
    *,
    existing_lat: float | None = None,
    existing_lng: float | None = None,
) -> dict[str, Any]:
    """Return coordinates and metadata; never requires manual GPS entry."""
    result: dict[str, Any] = {
        "lat": existing_lat,
        "lng": existing_lng,
        "source": None,
        "source_label": None,
        "confidence": 0.0,
        "survey_number": survey_number,
        "land_record": None,
    }

    land = registry.find_land_record(survey_number, property_address)
    if land and land.get("lat") and land.get("lng"):
        result.update(
            lat=land["lat"],
            lng=land["lng"],
            source="land_registry",
            source_label=f"Land registry — Survey {land['survey_number']}",
            confidence=0.95,
            survey_number=land["survey_number"],
            land_record=land,
        )
        return result

    geo = _from_pincode(property_address or "")
    if geo:
        result.update(**geo)
        return result

    if existing_lat and existing_lng:
        result.update(
            source="stored",
            source_label="Previously resolved coordinates",
            confidence=0.5,
        )
    return result
