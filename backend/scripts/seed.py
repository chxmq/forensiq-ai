"""Seed the database with realistic demo applications and run the full pipeline.

Creates a spread of scenarios that each exercise different detectors:
clean fast-track, forged title + ownership theft, income overstatement,
non-existent building (satellite), and encumbered/agricultural collateral.

Run:  backend/.venv/bin/python -m scripts.seed
"""
from __future__ import annotations

import asyncio
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure the backend root is importable when run as a module or a file.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import settings  # noqa: E402
from app.db import models  # noqa: E402
from app.db.database import SessionLocal, engine, init_db  # noqa: E402
from app.services.pipeline.orchestrator import run_analysis  # noqa: E402
from scripts import generate_samples  # noqa: E402


SCENARIOS = [
    {
        "applicant_name": "Ramesh Kumar Sharma",
        "applicant_pan": "ABCPS1234K",
        "loan_type": "home_loan",
        "loan_amount": 4_000_000,
        "declared_income": 1_500_000,
        "property_address": "Plot 142/3, Whitefield, Bengaluru, Karnataka 560066",
        "property_lat": 12.9698, "property_lng": 77.7499,
        "docs": [("clean_title", "land_title"), ("stmt_genuine", "bank_statement")],
    },
    {
        "applicant_name": "Suresh Sharma",
        "applicant_pan": "ABCPS1234K",  # same PAN, different name → identity theft signal
        "loan_type": "home_loan",
        "loan_amount": 9_000_000,
        "declared_income": 1_200_000,
        "property_address": "Plot 142/3, Whitefield, Bengaluru, Karnataka 560066",
        "property_lat": 12.9698, "property_lng": 77.7499,
        "docs": [("tampered_title", "land_title"), ("stmt_fabricated", "bank_statement")],
    },
    {
        "applicant_name": "Anita Desai",
        "applicant_pan": "BNZPA9087Q",
        "loan_type": "business_loan",
        "loan_amount": 15_000_000,
        "declared_income": 12_000_000,  # vs tax-reported 4.2M
        "property_address": "305/2B, MG Road, Pune, Maharashtra 411001",
        "property_lat": 18.5167, "property_lng": 73.8784,
        "docs": [("tampered_income", "salary_slip"), ("stmt_fabricated", "bank_statement")],
    },
    {
        "applicant_name": "Mohammed Irfan Khan",
        "applicant_pan": "CDEPK7766L",
        "loan_type": "home_loan",
        "loan_amount": 6_000_000,
        "declared_income": 1_800_000,
        "property_address": "210/5, Gachibowli, Hyderabad, Telangana 500032",
        "property_lat": 17.4401, "property_lng": 78.3489,
        "docs": [("gis_title", "land_title"), ("stmt_genuine", "bank_statement")],
    },
    {
        "applicant_name": "Lakshmi Narayan Reddy",
        "applicant_pan": "AXTPR5521M",
        "loan_type": "home_loan",
        "loan_amount": 2_500_000,
        "declared_income": 600_000,
        "property_address": "Survey 88/1, Devanahalli, Bengaluru Rural, Karnataka 562110",
        "property_lat": 13.2437, "property_lng": 77.7115,
        "docs": [("agri_title", "land_title"), ("stmt_genuine", "bank_statement")],
    },
]


def _reference(n: int) -> str:
    return f"APP-{datetime.now(timezone.utc).year}-{n:05d}"


def reset_db() -> None:
    models.Base = models.Application.__mro__  # noqa: F841  (touch to ensure import)
    from app.db.database import Base

    Base.metadata.drop_all(bind=engine)
    init_db()


async def main() -> None:
    print("• Generating sample documents...")
    samples = generate_samples.generate_all()

    print("• Resetting database...")
    reset_db()

    db = SessionLocal()
    created: list[str] = []
    try:
        for i, sc in enumerate(SCENARIOS, start=1):
            app = models.Application(
                reference=_reference(i),
                applicant_name=sc["applicant_name"],
                applicant_pan=sc["applicant_pan"],
                loan_type=sc["loan_type"],
                loan_amount=sc["loan_amount"],
                declared_income=sc["declared_income"],
                property_address=sc["property_address"],
                property_lat=sc["property_lat"],
                property_lng=sc["property_lng"],
                status=models.ApplicationStatus.draft,
            )
            db.add(app)
            db.flush()

            dest_dir = settings.upload_dir / app.id
            dest_dir.mkdir(parents=True, exist_ok=True)
            for sample_key, doc_type in sc["docs"]:
                src = samples[sample_key]
                doc = models.Document(
                    application_id=app.id, doc_type=doc_type,
                    filename=src.name,
                    stored_path="",
                    mime_type="image/jpeg" if src.suffix == ".jpg" else "text/csv",
                )
                db.add(doc)
                db.flush()
                target = dest_dir / f"{doc.id}_{src.name}"
                shutil.copyfile(src, target)
                doc.stored_path = str(target)
                doc.size_bytes = target.stat().st_size
            db.add(models.AuditEvent(application_id=app.id, actor="system",
                                     action="seeded", detail="Demo application seeded."))
            db.commit()
            created.append(app.id)
            print(f"  - Seeded {app.reference}: {app.applicant_name}")
    finally:
        db.close()

    # Analyze the first four synchronously (populate dashboard); leave the last
    # one un-analyzed so the live real-time demo has a fresh application to run.
    print("• Running analysis pipeline on seeded applications...")
    for app_id in created[:-1]:
        await run_analysis(app_id)

    db = SessionLocal()
    try:
        print("\nResults:")
        for app in db.query(models.Application).order_by(models.Application.reference).all():
            band = app.risk_band.value if app.risk_band else "—"
            print(f"  {app.reference}  {app.applicant_name:24s}  "
                  f"score={app.risk_score:5.1f}  band={band:8s}  status={app.status.value}")
    finally:
        db.close()
    print("\n✓ Seed complete. The last application is left un-analyzed for a live demo.")


if __name__ == "__main__":
    asyncio.run(main())
