"""Per-document forensic orchestrator.

Runs the appropriate detectors for the document type, extracts text/fields and
produces a single integrity score plus structured evidence for one document.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from app.services.common import Finding, ModuleResult, Severity
from app.services.forensics import image_forensics, ocr, pdf_forensics

IMAGE_MIME = {"image/jpeg", "image/jpg", "image/png", "image/tiff", "image/bmp", "image/webp"}
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".webp"}


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _is_image(path: Path, mime: str) -> bool:
    return mime in IMAGE_MIME or path.suffix.lower() in IMAGE_EXT


def _is_pdf(path: Path, mime: str) -> bool:
    return mime == "application/pdf" or path.suffix.lower() == ".pdf"


def analyze_document(path: Path, mime: str, doc_id: str) -> dict[str, Any]:
    result = ModuleResult(module="forensics")
    metrics: dict[str, Any] = {}
    artifacts: dict[str, str] = {}

    if _is_image(path, mime):
        out = image_forensics.analyze_image(path, doc_id)
        for f in out["findings"]:
            result.add(f)
        metrics.update(out["metrics"])
        artifacts.update(out["artifacts"])
        metrics["analyzed_as"] = "image"
    elif _is_pdf(path, mime):
        out = pdf_forensics.analyze_pdf(path, doc_id)
        for f in out["findings"]:
            result.add(f)
        metrics.update(out["metrics"])
        artifacts.update(out["artifacts"])
        metrics["analyzed_as"] = "pdf"
    else:
        result.status = "skipped"
        metrics["analyzed_as"] = "unsupported"

    # Text & field extraction (used downstream by verification/financial).
    text, ocr_status = ocr.extract_text(path, mime)
    fields = ocr.extract_fields(text)
    metrics["ocr"] = ocr_status

    if not ocr_status.get("ok") and result.status != "skipped":
        result.add(Finding(
            module="forensics",
            code="OCR_EXTRACTION_FAILED",
            title="Document text could not be extracted",
            detail=ocr_status.get("warning") or "OCR did not recover readable text from this file.",
            severity=Severity.medium,
            confidence=0.9,
            evidence={"engine": ocr_status.get("engine"), "filename": path.name},
        ))

    integrity = result.compute_score()

    return {
        "integrity_score": integrity,
        "findings": [f.to_dict() for f in result.findings],
        "raw_findings": result.findings,  # for the aggregator
        "metrics": metrics,
        "artifacts": artifacts,
        "extracted_text": text,
        "extracted_fields": fields,
    }
