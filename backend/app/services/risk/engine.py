"""Explainable risk intelligence.

Fuses the four module scores into a single, defensible underwriting decision and
— crucially — produces a human-readable rationale and a cross-source
contradiction summary. The goal is an *explainable* alert, not an opaque score:
every point of risk traces back to specific findings and evidence.
"""
from __future__ import annotations

from typing import Any

from app.core.config import settings
from app.services.common import ModuleResult, Severity, band_for_score

MODULE_LABEL = {
    "forensics": "Document Forensics",
    "financial": "Financial Integrity",
    "verification": "Cross-Source Verification",
    "gis": "GIS / Satellite Validation",
    "intake": "Document Pack Completeness",
}


def _recommendation(score: float, has_critical: bool, block_auto_clear: bool = False) -> tuple[str, str]:
    if has_critical or score >= settings.threshold_escalate:
        return "decline_or_escalate", "Auto-escalated to fraud investigation"
    if score >= settings.threshold_review:
        return "manual_review", "Routed for manual underwriting review"
    if block_auto_clear:
        return "manual_review", "Incomplete evidence — manual review required"
    if score >= settings.threshold_approve:
        return "review_light", "Eligible for review with conditions"
    return "auto_clear", "Eligible for fast-track approval"


def _narrative(modules: dict[str, ModuleResult], score: float, band: str,
               critical_count: int, high_count: int) -> str:
    parts: list[str] = []
    parts.append(
        f"The application carries an overall integrity risk of {score:.0f}/100 "
        f"({band.upper()}). "
    )
    if critical_count:
        parts.append(
            f"{critical_count} critical contradiction(s) were detected that "
            "directly undermine the legal/financial narrative. "
        )
    elif high_count:
        parts.append(f"{high_count} high-severity issue(s) require attention. ")

    drivers = sorted(modules.values(), key=lambda m: m.score, reverse=True)
    top = [m for m in drivers if m.score > 0][:2]
    if top:
        driver_txt = "; ".join(
            f"{MODULE_LABEL[m.module]} ({m.score:.0f}/100)" for m in top
        )
        parts.append(f"Primary risk drivers: {driver_txt}. ")
    else:
        parts.append("No material risk signals were raised across any module. ")
    return "".join(parts)


def _module_weights() -> dict[str, float]:
    return {
        "forensics": settings.weight_document,
        "financial": settings.weight_financial,
        "verification": settings.weight_verification,
        "gis": settings.weight_gis,
        "intake": settings.weight_intake,
    }


def aggregate(modules: dict[str, ModuleResult]) -> dict[str, Any]:
    weights = _module_weights()
    # Weighted base score across available modules (re-normalise weights to the
    # modules that actually ran).
    active = {k: v for k, v in modules.items() if v.status != "skipped"}
    total_w = sum(weights[k] for k in active) or 1.0
    base = sum(modules[k].score * weights[k] for k in active) / total_w if active else 0.0

    all_findings = [f for m in modules.values() for f in m.findings]
    critical = [f for f in all_findings if f.severity == Severity.critical]
    high = [f for f in all_findings if f.severity == Severity.high]

    # Critical findings impose a floor — a single confirmed contradiction (e.g.
    # ownership mismatch, non-existent property) must not be diluted by clean
    # scores elsewhere.
    score = base
    if critical:
        score = max(score, 78.0 + min(12.0, 3.0 * len(critical)))
    elif len(high) >= 2:
        score = max(score, 62.0)

    intake_mod = modules.get("intake")
    block_auto_clear = bool(intake_mod and intake_mod.metrics.get("block_auto_clear"))
    if block_auto_clear:
        score = max(score, 45.0)

    score = round(min(100.0, score), 2)

    band = band_for_score(score)
    rec_code, rec_label = _recommendation(score, bool(critical), block_auto_clear)

    # Contradiction summary across sources (the headline for underwriters).
    contradictions = [
        {
            "module": f.module,
            "module_label": MODULE_LABEL.get(f.module, f.module),
            "title": f.title,
            "detail": f.detail,
            "severity": f.severity.value,
            "confidence": round(f.confidence, 2),
        }
        for f in sorted(all_findings, key=lambda x: (-x.severity.rank, -x.confidence))
        if f.severity.rank >= Severity.high.rank
    ]

    narrative = _narrative(modules, score, band, len(critical), len(high))

    return {
        "risk_score": score,
        "risk_band": band,
        "recommendation": rec_code,
        "recommendation_label": rec_label,
        "narrative": narrative,
        "module_scores": {k: round(modules[k].score, 2) for k in modules},
        "module_weights": weights,
        "counts": {
            "critical": len(critical),
            "high": len(high),
            "total": len(all_findings),
        },
        "evidence_sufficient": not block_auto_clear,
        "contradiction_summary": contradictions,
        "modules": {k: v.to_dict() for k, v in modules.items()},
    }
