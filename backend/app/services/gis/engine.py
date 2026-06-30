"""GIS & satellite validation.

Verifies that the *claimed* nature of the collateral property is physically
corroborated by independent remote-sensing observations. This is what catches
fraud such as a "residential property" loan secured against what is actually
vacant land, agricultural land, a water body or protected forest.

The observations stand in for a satellite land-use classification API
(built-up ratio, NDVI vegetation index, water ratio, structure count and
change-detection). The frontend renders an offline procedural satellite view
from these metrics (no live map tiles — works fully offline).
"""
from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from app.core.config import settings
from app.services.common import Finding, ModuleResult, Severity
from app.services.gis.geocode import resolve_property_location
from app.services.verification import registry

# Which observed classes are compatible with a claimed usage.
COMPATIBLE = {
    "residential": {"residential"},
    "commercial": {"commercial", "residential"},
    "agricultural": {"agricultural", "vacant"},
    "industrial": {"industrial", "commercial"},
}


@lru_cache
def _observations() -> dict[str, dict]:
    path = settings.data_dir / "registries" / "gis_observations.json"
    if not path.exists():
        return {}
    data = json.loads(path.read_text())
    return {r["survey_number"]: r for r in data.get("records", [])}


def analyze_gis(application: dict, extracted_fields: dict) -> ModuleResult:
    result = ModuleResult(module="gis")

    survey = extracted_fields.get("survey_number")
    geo = resolve_property_location(
        application.get("property_address"),
        survey,
        existing_lat=application.get("property_lat"),
        existing_lng=application.get("property_lng"),
    )
    land = geo.get("land_record") or registry.find_land_record(survey, application.get("property_address"))
    obs = _observations().get(land["survey_number"]) if land else None

    lat, lng = geo.get("lat"), geo.get("lng")
    result.metrics["coordinates"] = {"lat": lat, "lng": lng}
    result.metrics["geocode"] = {
        "source": geo.get("source"),
        "source_label": geo.get("source_label"),
        "confidence": geo.get("confidence"),
        "survey_number": geo.get("survey_number") or survey,
    }
    result.metrics["satellite_available"] = bool(obs)

    if not obs:
        result.status = "skipped"
        if lat and lng:
            result.summary = (
                f"Parcel located via {geo.get('source_label') or 'address'}. "
                "No satellite observation on file for this survey."
            )
            result.add(Finding(
                module="gis",
                code="SATELLITE_OBSERVATION_UNAVAILABLE",
                title="Satellite land-use observation not on file",
                detail=(
                    f"Coordinates resolved ({lat:.4f}, {lng:.4f}) but no bundled "
                    "satellite classification exists for this survey number. GIS "
                    "contradiction checks were not performed — manual site verification "
                    "recommended."
                ),
                severity=Severity.medium,
                confidence=0.7,
                evidence={"survey_number": survey, "lat": lat, "lng": lng},
            ))
        else:
            result.summary = (
                "Could not locate parcel — add property address or upload land title "
                "with survey/plot number for automatic GIS validation."
            )
            result.add(Finding(
                module="gis",
                code="PARCEL_NOT_LOCATED",
                title="Property could not be geolocated for satellite check",
                detail=(
                    "No coordinates or survey number could be resolved from the "
                    "application or uploaded land documents. Satellite validation "
                    "was skipped."
                ),
                severity=Severity.medium,
                confidence=0.75,
                evidence={"address": application.get("property_address")},
            ))
        result.metrics["map"] = {"lat": lat, "lng": lng, "zoom": 16} if lat and lng else None
        result.compute_score()
        return result

    claimed = (land.get("property_type") if land else None) or "residential"
    observed = obs["observed_land_use"]
    result.metrics.update(
        claimed_use=claimed,
        observed_use=observed,
        built_up_ratio=obs["built_up_ratio"],
        ndvi=obs["ndvi"],
        water_ratio=obs["water_ratio"],
        structures_detected=obs["structures_detected"],
        change_since_prior=obs["change_since_prior"],
        imagery_date=obs["imagery_date"],
        map={"lat": lat, "lng": lng, "zoom": 17},
    )

    compatible = observed in COMPATIBLE.get(claimed, {claimed})

    if not compatible:
        # Tailor the message to the contradiction type.
        if claimed in ("residential", "commercial") and obs["structures_detected"] == 0:
            detail = (
                f"The application/record describes a {claimed} property, but satellite "
                f"imagery ({obs['imagery_date']}) shows no structures (built-up ratio "
                f"{obs['built_up_ratio']:.0%}) and classifies the parcel as '{observed}'. "
                "The claimed building does not physically exist."
            )
            sev = Severity.critical
        elif observed in ("forest", "water"):
            detail = (
                f"Parcel is claimed as {claimed} but remote sensing classifies it as "
                f"'{observed}' (NDVI {obs['ndvi']:.2f}). Such land is typically protected / "
                "non-developable."
            )
            sev = Severity.critical
        else:
            detail = (
                f"Claimed land use '{claimed}' contradicts the satellite-observed land use "
                f"'{observed}' (built-up {obs['built_up_ratio']:.0%}, NDVI {obs['ndvi']:.2f})."
            )
            sev = Severity.high
        result.add(Finding(
            module="gis", code="LANDUSE_CONTRADICTION",
            title=f"Satellite imagery contradicts claimed land use ({claimed} vs {observed})",
            detail=detail, severity=sev, confidence=0.82,
            evidence={k: obs[k] for k in ("observed_land_use", "built_up_ratio", "ndvi",
                                          "structures_detected", "imagery_date")},
        ))

    if obs["change_since_prior"] == "new_clearing":
        result.add(Finding(
            module="gis", code="RECENT_LAND_CHANGE",
            title="Recent land alteration detected",
            detail=(
                "Change-detection between satellite passes shows recent clearing/alteration "
                "of the parcel, which can indicate hurried preparation to support a fraudulent "
                "valuation or claim."
            ),
            severity=Severity.medium, confidence=0.6,
            evidence={"change": obs["change_since_prior"], "imagery_date": obs["imagery_date"]},
        ))

    result.compute_score()
    result.summary = (
        f"Satellite check: claimed '{claimed}' vs observed '{observed}'. "
        + ("Contradiction detected." if result.findings else "Consistent.")
    )
    return result
