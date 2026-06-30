"""Investigation case management endpoints."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.core.auth import CurrentUser
from app.db import models
from app.db.database import get_db
from app.schemas.api import CaseOut, CaseUpdate

router = APIRouter(prefix="/api/cases", tags=["cases"])
DbSession = Annotated[Session, Depends(get_db)]


def _case_out(case: models.Case) -> CaseOut:
    app = case.application
    return CaseOut(
        id=case.id,
        case_number=case.case_number,
        status=case.status.value,
        priority=case.priority.value,
        assignee=case.assignee,
        summary=case.summary,
        resolution_note=case.resolution_note,
        application_id=case.application_id,
        applicant_name=app.applicant_name if app else None,
        application_reference=app.reference if app else None,
        created_at=case.created_at,
        updated_at=case.updated_at,
    )


@router.get("", response_model=list[CaseOut])
def list_cases(
    db: DbSession,
    _user: CurrentUser,
    status: str | None = None,
):
    q = db.query(models.Case).options(joinedload(models.Case.application))
    if status:
        q = q.filter(models.Case.status == models.CaseStatus(status))
    return [_case_out(c) for c in q.order_by(models.Case.created_at.desc()).all()]


@router.get("/{case_id}", response_model=CaseOut)
def get_case(
    case_id: str,
    db: DbSession,
    _user: CurrentUser,
) -> CaseOut:
    case = (
        db.query(models.Case)
        .options(joinedload(models.Case.application))
        .filter(models.Case.id == case_id)
        .first()
    )
    if case is None:
        raise HTTPException(404, "Case not found")
    return _case_out(case)


@router.patch("/{case_id}", response_model=CaseOut)
def update_case(
    case_id: str,
    payload: CaseUpdate,
    db: DbSession,
    user: CurrentUser,
) -> CaseOut:
    case = (
        db.query(models.Case)
        .options(joinedload(models.Case.application))
        .filter(models.Case.id == case_id)
        .first()
    )
    if case is None:
        raise HTTPException(404, "Case not found")

    if payload.status:
        case.status = models.CaseStatus(payload.status)
    if payload.assignee is not None:
        case.assignee = payload.assignee
    if payload.resolution_note is not None:
        case.resolution_note = payload.resolution_note

    db.add(models.AuditEvent(
        application_id=case.application_id,
        actor=payload.assignee or user,
        action="case_updated",
        detail=f"Status={case.status.value}; {payload.resolution_note or ''}",
    ))
    db.commit()
    db.refresh(case)
    return _case_out(case)
