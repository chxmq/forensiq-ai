"""End-to-end analysis pipeline.

Orchestrates every engine for an application, streams real-time progress over
WebSockets, persists per-document forensics, findings and the aggregated risk
report, then applies the escalation policy. Designed to run inside a background
task so the API responds immediately and the UI watches it live.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.db import models
from app.db.database import SessionLocal
from app.services.common import ModuleResult, Finding, Severity
from app.services.escalation import engine as escalation
from app.services.financial import engine as financial
from app.services.financial import parser as fin_parser
from app.services.forensics import engine as forensics
from app.services.gis import engine as gis
from app.services.intake import engine as intake
from app.services.gis.geocode import resolve_property_location
from app.services.pipeline.ws_manager import manager, GLOBAL_ROOM
from app.services.risk import engine as risk
from app.services.verification import engine as verification

CSV_EXT = {".csv", ".txt"}
_running: set[str] = set()

# Pipeline stages for the progress bar (label + weight toward 100%).
STAGES = [
    ("ingest", "Ingesting & hashing documents", 8),
    ("forensics", "Running document forensics", 32),
    ("extract", "Extracting & consolidating fields", 10),
    ("intake", "Checking document pack completeness", 8),
    ("financial", "Analyzing financial integrity", 14),
    ("verification", "Cross-verifying trusted sources", 16),
    ("gis", "Validating GIS / satellite imagery", 10),
    ("risk", "Synthesizing explainable risk", 4),
    ("escalation", "Applying decision & escalation policy", 2),
]


async def _emit(app_id: str, event: str, payload: dict[str, Any]) -> None:
    message = {"type": event, "application_id": app_id, **payload}
    await manager.broadcast(app_id, message)
    if event in ("stage", "completed", "finding"):
        await manager.broadcast(GLOBAL_ROOM, message)


def _is_csv(doc: models.Document) -> bool:
    return Path(doc.stored_path).suffix.lower() in CSV_EXT or doc.mime_type in (
        "text/csv", "text/plain", "application/csv",
    )


async def run_analysis(application_id: str) -> None:
    """Run the full pipeline; safe to launch as a fire-and-forget task."""
    if application_id in _running:
        return
    _running.add(application_id)
    db: Session = SessionLocal()
    progress = 0
    try:
        app = db.get(models.Application, application_id)
        if app is None:
            return
        app.status = models.ApplicationStatus.analyzing
        db.commit()

        await _emit(application_id, "started", {
            "reference": app.reference, "applicant": app.applicant_name,
            "stages": [{"key": s[0], "label": s[1]} for s in STAGES],
        })

        async def stage(key: str, label: str, weight: int) -> None:
            nonlocal progress
            progress += weight
            await _emit(application_id, "stage", {
                "stage": key, "label": label, "progress": min(progress, 100),
            })
            await asyncio.sleep(0.35)  # let the UI render the live step

        # ── 1. Ingest ──────────────────────────────────────────
        await stage(*STAGES[0])
        documents = list(app.documents)
        for doc in documents:
            p = Path(doc.stored_path)
            if p.exists():
                doc.sha256 = forensics.sha256_of(p)
        db.commit()

        # ── 2. Forensics (per document) ────────────────────────
        await stage(*STAGES[1])
        forensic_findings: list[Finding] = []
        forensic_metrics: dict[str, Any] = {"documents": []}
        for doc in documents:
            p = Path(doc.stored_path)
            if not p.exists():
                continue
            res = forensics.analyze_document(p, doc.mime_type, doc.id)
            doc.integrity_score = res["integrity_score"]
            doc.extracted_text = res["extracted_text"][:20000] if res["extracted_text"] else None
            doc.extracted_fields = res["extracted_fields"]
            doc.forensics = {"metrics": res["metrics"], "findings": res["findings"]}
            doc.artifacts = res["artifacts"]
            forensic_findings.extend(res["raw_findings"])
            forensic_metrics["documents"].append({
                "document_id": doc.id, "filename": doc.filename,
                "doc_type": doc.doc_type, "integrity_score": doc.integrity_score,
                "artifacts": res["artifacts"],
            })
            for rf in res["raw_findings"]:
                await _emit(application_id, "finding", {
                    "module": "forensics", "title": rf.title,
                    "severity": rf.severity.value, "document": doc.filename,
                })
            await asyncio.sleep(0.15)
        db.commit()

        forensic_result = ModuleResult(module="forensics", findings=forensic_findings,
                                       metrics=forensic_metrics)
        forensic_result.compute_score()
        forensic_result.summary = (
            f"Analyzed {len(documents)} document(s); "
            f"{len(forensic_findings)} integrity issue(s) found."
        )

        # ── 3. Consolidate extracted fields & transactions ─────
        await stage(*STAGES[2])
        consolidated: dict[str, Any] = {}
        transactions: list[dict] = []
        for doc in documents:
            if doc.extracted_fields:
                for k, v in doc.extracted_fields.items():
                    consolidated.setdefault(k, v)
            if _is_csv(doc):
                p = Path(doc.stored_path)
                if p.exists():
                    transactions.extend(fin_parser.parse_csv_file(p))

        app_dict = {
            "applicant_name": app.applicant_name,
            "applicant_pan": app.applicant_pan,
            "loan_type": app.loan_type,
            "loan_amount": app.loan_amount,
            "declared_income": app.declared_income,
            "property_address": app.property_address,
            "property_lat": app.property_lat,
            "property_lng": app.property_lng,
        }

        doc_field_list = [
            {
                "doc_type": d.doc_type,
                "filename": d.filename,
                "fields": d.extracted_fields or {},
            }
            for d in documents
        ]

        # ── 4. Intake completeness ─────────────────────────────
        await stage(*STAGES[3])
        financial_will_skip = not transactions
        intake_result = intake.analyze_intake(app_dict, doc_field_list, financial_will_skip)
        for f in intake_result.findings:
            await _emit(application_id, "finding", {
                "module": "intake", "title": f.title,
                "severity": f.severity.value,
            })

        # ── 5. Financial integrity ───────────────────────────────
        await stage(*STAGES[4])
        financial_result = financial.analyze_financials(
            transactions, app.declared_income, app.loan_amount, doc_field_list,
        )

        # ── 6. Cross-source verification ───────────────────────
        await stage(*STAGES[5])
        verification_result = verification.analyze_verification(app_dict, consolidated)

        # ── 7. GIS / satellite ─────────────────────────────────
        await stage(*STAGES[6])
        geo = resolve_property_location(
            app.property_address,
            consolidated.get("survey_number"),
            existing_lat=app.property_lat,
            existing_lng=app.property_lng,
        )
        if geo.get("lat") and geo.get("lng"):
            app.property_lat = geo["lat"]
            app.property_lng = geo["lng"]
            db.commit()
            app_dict["property_lat"] = geo["lat"]
            app_dict["property_lng"] = geo["lng"]

        gis_result = gis.analyze_gis(app_dict, consolidated)

        # ── 8. Risk synthesis ──────────────────────────────────
        await stage(*STAGES[7])
        modules = {
            "forensics": forensic_result,
            "intake": intake_result,
            "financial": financial_result,
            "verification": verification_result,
            "gis": gis_result,
        }
        report = risk.aggregate(modules)

        # Persist findings.
        db.query(models.Finding).filter(models.Finding.application_id == app.id).delete()
        for mod in modules.values():
            for f in mod.findings:
                db.add(models.Finding(
                    application_id=app.id, module=f.module, code=f.code,
                    title=f.title, detail=f.detail,
                    severity=models.RiskBand(f.severity.value),
                    confidence=f.confidence, evidence=f.evidence,
                ))

        app.risk_score = report["risk_score"]
        app.risk_band = models.RiskBand(report["risk_band"])
        app.recommendation = report["recommendation"]
        app.report = report
        app.status = models.ApplicationStatus.analyzed
        db.commit()

        # ── 9. Escalation policy ───────────────────────────────
        await stage(*STAGES[8])
        decision = escalation.apply_policy(db, app, report)
        db.commit()

        await _emit(application_id, "completed", {
            "risk_score": report["risk_score"],
            "risk_band": report["risk_band"],
            "recommendation": report["recommendation"],
            "recommendation_label": report["recommendation_label"],
            "status": app.status.value,
            "case_number": decision.get("case_number"),
            "counts": report["counts"],
            "progress": 100,
        })
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        app = db.get(models.Application, application_id)
        if app:
            app.status = models.ApplicationStatus.failed
            db.add(models.AuditEvent(
                application_id=app.id, actor="system", action="analysis_error",
                detail=str(exc),
            ))
            db.commit()
        await _emit(application_id, "error", {"message": str(exc), "progress": progress})
    finally:
        _running.discard(application_id)
        db.close()
