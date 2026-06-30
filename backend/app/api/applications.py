"""Application lifecycle endpoints: create, upload, analyze, inspect, decide."""
from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db import models
from app.db.database import get_db
from app.schemas.api import (
    ApplicationCreate,
    ApplicationDetail,
    ApplicationSummary,
    DecisionUpdate,
)
from app.services.gis.geocode import resolve_property_location
from app.services.pipeline.orchestrator import run_analysis

router = APIRouter(prefix="/api/applications", tags=["applications"])


def _reference(db: Session) -> str:
    year = datetime.now(timezone.utc).year
    n = db.query(models.Application).count() + 1
    return f"APP-{year}-{n:05d}"


@router.post("", response_model=ApplicationDetail, status_code=201)
def create_application(payload: ApplicationCreate, db: Session = Depends(get_db)) -> models.Application:
    app = models.Application(
        reference=_reference(db),
        applicant_name=payload.applicant_name,
        applicant_pan=payload.applicant_pan,
        loan_type=payload.loan_type,
        loan_amount=payload.loan_amount,
        declared_income=payload.declared_income,
        property_address=payload.property_address,
        property_lat=payload.property_lat,
        property_lng=payload.property_lng,
        status=models.ApplicationStatus.draft,
    )
    if payload.property_address and not (payload.property_lat and payload.property_lng):
        geo = resolve_property_location(payload.property_address, None)
        if geo.get("lat") and geo.get("lng"):
            app.property_lat = geo["lat"]
            app.property_lng = geo["lng"]
    db.add(app)
    db.flush()  # materialize the generated UUID before referencing app.id
    db.add(models.AuditEvent(application_id=app.id, actor="underwriter",
                             action="application_created",
                             detail=f"Application {app.reference} created."))
    db.commit()
    db.refresh(app)
    return app


@router.get("", response_model=list[ApplicationSummary])
def list_applications(status: str | None = None, db: Session = Depends(get_db)):
    q = db.query(models.Application)
    if status:
        q = q.filter(models.Application.status == models.ApplicationStatus(status))
    return q.order_by(models.Application.created_at.desc()).all()


@router.get("/{application_id}", response_model=ApplicationDetail)
def get_application(application_id: str, db: Session = Depends(get_db)) -> models.Application:
    app = db.get(models.Application, application_id)
    if app is None:
        raise HTTPException(404, "Application not found")
    return app


@router.post("/{application_id}/documents", response_model=ApplicationDetail)
async def upload_documents(
    application_id: str,
    files: list[UploadFile] = File(...),
    doc_types: str | None = Form(None),
    db: Session = Depends(get_db),
) -> models.Application:
    app = db.get(models.Application, application_id)
    if app is None:
        raise HTTPException(404, "Application not found")

    types = [t.strip() for t in doc_types.split(",")] if doc_types else []
    dest_dir = settings.upload_dir / application_id
    dest_dir.mkdir(parents=True, exist_ok=True)

    for idx, uf in enumerate(files):
        safe_name = Path(uf.filename or f"file_{idx}").name
        doc = models.Document(
            application_id=app.id,
            doc_type=types[idx] if idx < len(types) else "unknown",
            filename=safe_name,
            stored_path="",
            mime_type=uf.content_type or "application/octet-stream",
        )
        db.add(doc)
        db.flush()  # get doc.id
        target = dest_dir / f"{doc.id}_{safe_name}"
        with target.open("wb") as out:
            shutil.copyfileobj(uf.file, out)
        doc.stored_path = str(target)
        doc.size_bytes = target.stat().st_size

    db.add(models.AuditEvent(application_id=app.id, actor="underwriter",
                             action="documents_uploaded",
                             detail=f"{len(files)} document(s) uploaded."))
    db.commit()
    db.refresh(app)
    return app


@router.post("/{application_id}/analyze", response_model=ApplicationSummary)
async def analyze_application(
    application_id: str,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
) -> models.Application:
    app = db.get(models.Application, application_id)
    if app is None:
        raise HTTPException(404, "Application not found")
    if app.status == models.ApplicationStatus.analyzing:
        raise HTTPException(409, "Analysis already in progress")
    if not app.documents:
        raise HTTPException(400, "Upload at least one document before analysis")

    app.status = models.ApplicationStatus.analyzing
    db.commit()
    db.refresh(app)
    background.add_task(run_analysis, app.id)
    return app


@router.post("/batch-analyze")
async def batch_analyze(
    background: BackgroundTasks,
    db: Session = Depends(get_db),
) -> dict:
    """Queue analysis for all applications with documents but no completed report."""
    candidates = (
        db.query(models.Application)
        .filter(models.Application.risk_band.is_(None))
        .filter(models.Application.status != models.ApplicationStatus.analyzing)
        .all()
    )
    queued: list[str] = []
    for app in candidates:
        if not app.documents:
            continue
        app.status = models.ApplicationStatus.analyzing
        db.add(app)
        queued.append(app.id)
    db.commit()
    for app_id in queued:
        background.add_task(run_analysis, app_id)
    return {"queued": len(queued), "application_ids": queued}


@router.post("/{application_id}/decision", response_model=ApplicationDetail)
def record_decision(
    application_id: str, payload: DecisionUpdate, db: Session = Depends(get_db),
) -> models.Application:
    app = db.get(models.Application, application_id)
    if app is None:
        raise HTTPException(404, "Application not found")

    mapping = {
        "approved": models.ApplicationStatus.approved,
        "declined": models.ApplicationStatus.declined,
        "manual_review": models.ApplicationStatus.manual_review,
    }
    if payload.decision not in mapping:
        raise HTTPException(400, "Invalid decision")
    app.status = mapping[payload.decision]
    db.add(models.AuditEvent(application_id=app.id, actor=payload.actor,
                             action=f"decision_{payload.decision}",
                             detail=payload.note or ""))
    db.commit()
    db.refresh(app)
    return app


@router.delete("/{application_id}")
def delete_application(application_id: str, db: Session = Depends(get_db)) -> dict:
    app = db.get(models.Application, application_id)
    if app is None:
        raise HTTPException(404, "Application not found")
    db.delete(app)
    db.commit()
    return {"deleted": application_id}
