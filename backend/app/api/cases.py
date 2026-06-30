"""Investigation case management endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import models
from app.db.database import get_db
from app.schemas.api import CaseOut, CaseUpdate

router = APIRouter(prefix="/api/cases", tags=["cases"])


@router.get("", response_model=list[CaseOut])
def list_cases(status: str | None = None, db: Session = Depends(get_db)):
    q = db.query(models.Case)
    if status:
        q = q.filter(models.Case.status == models.CaseStatus(status))
    return q.order_by(models.Case.created_at.desc()).all()


@router.get("/{case_id}", response_model=CaseOut)
def get_case(case_id: str, db: Session = Depends(get_db)) -> models.Case:
    case = db.get(models.Case, case_id)
    if case is None:
        raise HTTPException(404, "Case not found")
    return case


@router.patch("/{case_id}", response_model=CaseOut)
def update_case(case_id: str, payload: CaseUpdate, db: Session = Depends(get_db)) -> models.Case:
    case = db.get(models.Case, case_id)
    if case is None:
        raise HTTPException(404, "Case not found")

    if payload.status:
        case.status = models.CaseStatus(payload.status)
    if payload.assignee is not None:
        case.assignee = payload.assignee
    if payload.resolution_note is not None:
        case.resolution_note = payload.resolution_note

    db.add(models.AuditEvent(
        application_id=case.application_id, actor=case.assignee or "investigator",
        action="case_updated",
        detail=f"Status={case.status.value}; {payload.resolution_note or ''}",
    ))
    db.commit()
    db.refresh(case)
    return case
