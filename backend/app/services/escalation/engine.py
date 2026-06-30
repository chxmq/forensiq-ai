"""Automated risk escalation & case management.

Applies the configured decision policy to a completed analysis: clears low-risk
applications for fast-track, routes medium risk to manual review, and
automatically opens an investigation case for high/critical risk — with a
priority derived from the risk band.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db import models


def _case_number(db: Session) -> str:
    year = datetime.now(timezone.utc).year
    count = db.query(models.Case).count() + 1
    return f"FRQ-{year}-{count:05d}"


def apply_policy(db: Session, app: models.Application, report: dict) -> dict:
    score = report["risk_score"]
    band = report["risk_band"]
    rec = report["recommendation"]
    critical = report["counts"]["critical"]

    decision = {"action": rec, "case_created": False, "case_number": None}

    if rec == "auto_clear":
        app.status = models.ApplicationStatus.auto_cleared
    elif rec in ("review_light", "manual_review"):
        app.status = models.ApplicationStatus.manual_review
    else:  # decline_or_escalate
        app.status = models.ApplicationStatus.escalated

    # Open an investigation case for escalated / critical applications.
    if app.status == models.ApplicationStatus.escalated and app.case is None:
        priority = models.RiskBand.critical if critical else models.RiskBand.high
        case = models.Case(
            application_id=app.id,
            case_number=_case_number(db),
            status=models.CaseStatus.open,
            priority=priority,
            summary=report.get("narrative"),
        )
        db.add(case)
        decision["case_created"] = True
        decision["case_number"] = case.case_number
        db.add(models.AuditEvent(
            application_id=app.id, actor="system",
            action="case_opened",
            detail=f"Auto-escalated ({band}, score {score:.0f}). Case {case.case_number} opened.",
        ))

    db.add(models.AuditEvent(
        application_id=app.id, actor="system",
        action="policy_applied",
        detail=f"Decision: {rec} | risk {score:.0f}/100 ({band}).",
    ))
    return decision


def estimated_exposure(app: models.Application) -> float:
    """Value at risk that an escalation prevents — used for dashboard metrics."""
    return float(app.loan_amount or 0)
