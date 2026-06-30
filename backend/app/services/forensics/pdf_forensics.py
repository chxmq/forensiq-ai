"""PDF structural forensics.

A PDF is an append-friendly format: edits are often written as *incremental
updates* appended after the original ``%%EOF``. Counting end-of-file markers,
cross-reference sections and comparing the document metadata reveals whether a
"final" PDF was modified after it was first produced/signed — one of the most
common ways financial statements and legal agreements are tampered with.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from app.services.common import Finding, Severity

EDITING_PRODUCERS = (
    "photoshop", "gimp", "illustrator", "word", "libreoffice", "openoffice",
    "pdfescape", "ilovepdf", "smallpdf", "sejda", "pdf-xchange", "foxit phantom",
    "nitro", "soda pdf", "canva",
)


def _date(raw: Any) -> str | None:
    if not raw:
        return None
    return str(raw).replace("D:", "").strip()


def analyze_pdf(path: Path, doc_id: str) -> dict[str, Any]:
    findings: list[Finding] = []
    metrics: dict[str, Any] = {}

    raw = path.read_bytes()

    eof_count = len(re.findall(rb"%%EOF", raw))
    startxref_count = len(re.findall(rb"startxref", raw))
    metrics["eof_markers"] = eof_count
    metrics["startxref_markers"] = startxref_count
    metrics["has_javascript"] = bool(re.search(rb"/JavaScript|/JS\b", raw))
    metrics["has_acroform"] = bool(re.search(rb"/AcroForm", raw))
    metrics["has_annotations"] = bool(re.search(rb"/Annots", raw))

    # Incremental updates: more than one EOF marker ⇒ appended revisions.
    if eof_count > 1:
        sev = Severity.high if eof_count > 2 else Severity.medium
        findings.append(
            Finding(
                module="forensics",
                code="PDF_INCREMENTAL_UPDATE",
                title=f"PDF modified after creation ({eof_count - 1} revision(s) appended)",
                detail=(
                    f"The file contains {eof_count} end-of-file markers, meaning content "
                    f"was appended {eof_count - 1} time(s) after the original document "
                    "was finalized. Incremental updates are how text/figures in a signed "
                    "or 'final' PDF get silently altered."
                ),
                severity=sev,
                confidence=0.8,
                evidence={"eof_markers": eof_count, "startxref_markers": startxref_count},
            )
        )

    if metrics["has_javascript"]:
        findings.append(
            Finding(
                module="forensics",
                code="PDF_JAVASCRIPT",
                title="Embedded JavaScript present in document",
                detail=(
                    "The PDF embeds JavaScript. Document statements/records normally "
                    "contain no executable code; this can indicate dynamic field "
                    "manipulation or an attempt to alter rendered values."
                ),
                severity=Severity.medium,
                confidence=0.6,
                evidence={},
            )
        )

    # Metadata via pikepdf (preferred) with a graceful fallback.
    try:
        import pikepdf

        with pikepdf.open(path) as pdf:
            docinfo = {str(k): str(v) for k, v in (pdf.docinfo or {}).items()}
            metrics["producer"] = docinfo.get("/Producer")
            metrics["creator"] = docinfo.get("/Creator")
            metrics["pages"] = len(pdf.pages)
            cdate = _date(docinfo.get("/CreationDate"))
            mdate = _date(docinfo.get("/ModDate"))
            metrics["creation_date"] = cdate
            metrics["mod_date"] = mdate

            producer = (docinfo.get("/Producer", "") + " " + docinfo.get("/Creator", "")).lower()
            if any(p in producer for p in EDITING_PRODUCERS):
                findings.append(
                    Finding(
                        module="forensics",
                        code="PDF_EDITOR_PRODUCER",
                        title="PDF produced/edited by a content-editing tool",
                        detail=(
                            f"Producer/Creator metadata ('{docinfo.get('/Producer')}') "
                            "indicates the document passed through an editor capable of "
                            "modifying text and figures, rather than a trusted issuing "
                            "system."
                        ),
                        severity=Severity.medium,
                        confidence=0.65,
                        evidence={"producer": docinfo.get("/Producer"), "creator": docinfo.get("/Creator")},
                    )
                )

            if cdate and mdate and cdate != mdate:
                findings.append(
                    Finding(
                        module="forensics",
                        code="PDF_DATE_MISMATCH",
                        title="Creation and modification dates differ",
                        detail=(
                            f"Document was created on {cdate} but last modified on {mdate}. "
                            "A trustworthy issued statement should not be modified after issuance."
                        ),
                        severity=Severity.low,
                        confidence=0.5,
                        evidence={"creation_date": cdate, "mod_date": mdate},
                    )
                )
    except Exception as exc:  # noqa: BLE001
        metrics["pdf_meta_error"] = str(exc)

    return {"findings": findings, "metrics": metrics, "artifacts": {}}
