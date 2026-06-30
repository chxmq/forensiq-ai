"""Aggregate dashboard metrics."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.auth import CurrentUser
from app.db import models
from app.db.database import get_db
from app.schemas.api import DashboardStats

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])
DbSession = Annotated[Session, Depends(get_db)]

S = models.ApplicationStatus


@router.get("", response_model=DashboardStats)
def dashboard(db: DbSession, _user: CurrentUser) -> DashboardStats:
    def count(*statuses) -> int:
        return db.query(models.Application).filter(
            models.Application.status.in_(statuses)
        ).count()

    total = db.query(models.Application).count()

    dist = {"low": 0, "medium": 0, "high": 0, "critical": 0}
    for band, c in (
        db.query(models.Application.risk_band, func.count())
        .filter(models.Application.risk_band.isnot(None))
        .group_by(models.Application.risk_band)
        .all()
    ):
        dist[band.value] = c

    avg = db.query(func.avg(models.Application.risk_score)).filter(
        models.Application.risk_score > 0
    ).scalar() or 0.0

    fraud_value = db.query(func.sum(models.Application.loan_amount)).filter(
        models.Application.status == S.escalated
    ).scalar() or 0.0

    total_findings = db.query(models.Finding).count()
    high_severity = db.query(models.Finding).filter(
        models.Finding.severity.in_([models.RiskBand.high, models.RiskBand.critical])
    ).count()

    pending = (
        db.query(models.Application)
        .filter(models.Application.risk_band.is_(None))
        .filter(models.Application.status.in_([S.draft, S.analyzed, S.failed]))
        .count()
    )

    recent = (
        db.query(models.Application)
        .order_by(models.Application.updated_at.desc())
        .limit(8)
        .all()
    )

    return DashboardStats(
        total_applications=total,
        analyzing=count(S.analyzing),
        auto_cleared=count(S.auto_cleared, S.approved),
        manual_review=count(S.manual_review),
        escalated=count(S.escalated, S.declined),
        failed=count(S.failed),
        open_cases=db.query(models.Case).filter(
            models.Case.status.in_([models.CaseStatus.open, models.CaseStatus.investigating])
        ).count(),
        avg_risk_score=round(float(avg), 1),
        fraud_prevented_value=float(fraud_value),
        risk_distribution=dist,
        total_findings=total_findings,
        high_severity_findings=high_severity,
        pending_analysis=pending,
        recent=recent,
    )
