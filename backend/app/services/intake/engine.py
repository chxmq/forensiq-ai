"""Application intake completeness & evidence sufficiency.

Random or incomplete document packs must not receive a low risk score.
This module enforces minimum underwriting evidence before auto-clear is allowed.
"""
from __future__ import annotations

from typing import Any

from app.services.common import Finding, ModuleResult, Severity
from app.data.document_types import INCOME_DOC_TYPES, IDENTITY_DOC_TYPES

COLLATERAL_TYPES = frozenset({
    "land_title", "sale_deed", "chain_document", "valuation_report",
    "plan_approval", "occupancy_certificate",
})

INCOME_TYPES = INCOME_DOC_TYPES

MIN_TEXT_CHARS = 80


def _has_type(documents: list[dict], *types: str) -> bool:
    present = {d.get("doc_type") for d in documents}
    return any(t in present for t in types)


def _total_text(documents: list[dict]) -> int:
    total = 0
    for d in documents:
        fields = d.get("extracted_fields") or {}
        total += int(fields.get("text_length") or 0)
    return total


def _extracted_signal(documents: list[dict]) -> dict[str, bool]:
    flags = {"pan": False, "amount": False, "survey": False, "owner": False, "dates": False}
    for d in documents:
        f = d.get("extracted_fields") or {}
        if f.get("pan"):
            flags["pan"] = True
        if f.get("max_amount") or f.get("amounts"):
            flags["amount"] = True
        if f.get("survey_number"):
            flags["survey"] = True
        if f.get("owner_name"):
            flags["owner"] = True
        if f.get("dates"):
            flags["dates"] = True
    return flags


def analyze_intake(application: dict, documents: list[dict], financial_skipped: bool) -> ModuleResult:
    """Validate document pack completeness and relevance."""
    result = ModuleResult(module="intake")
    loan = float(application.get("loan_amount") or 0)
    income = float(application.get("declared_income") or 0)
    loan_type = application.get("loan_type") or "home_loan"
    n_docs = len(documents)

    result.metrics["document_count"] = n_docs
    result.metrics["has_bank_statement"] = _has_type(documents, "bank_statement")
    result.metrics["has_income_proof"] = _has_type(documents, *INCOME_TYPES)
    result.metrics["has_identity_proof"] = _has_type(documents, *IDENTITY_DOC_TYPES)
    result.metrics["has_collateral_doc"] = _has_type(documents, *COLLATERAL_TYPES)
    result.metrics["total_extracted_text"] = _total_text(documents)

    signals = _extracted_signal(documents)
    result.metrics["extracted_signals"] = signals
    signal_count = sum(1 for v in signals.values() if v)

    other_only = n_docs > 0 and all(d.get("doc_type") in (None, "other", "unknown") for d in documents)

    # ── Required document classes ───────────────────────────────
    if income > 0 and not result.metrics["has_bank_statement"]:
        result.add(Finding(
            module="intake",
            code="MISSING_BANK_STATEMENT",
            title="Bank statement not provided",
            detail=(
                "Declared income requires salary credits to be verified against a bank "
                "statement. Canara underwriting cannot validate payslip/Form 16 claims "
                "without transaction evidence."
            ),
            severity=Severity.high,
            confidence=0.95,
            evidence={"declared_income": income},
        ))

    if income > 0 and not result.metrics["has_income_proof"]:
        result.add(Finding(
            module="intake",
            code="MISSING_INCOME_PROOF",
            title="Income proof document missing",
            detail=(
                "No salary slip, Form 16, ITR, or income certificate was uploaded. "
                "Income declared on the application cannot be corroborated."
            ),
            severity=Severity.medium,
            confidence=0.9,
        ))

    app_pan = (application.get("applicant_pan") or "").upper()
    if app_pan and not result.metrics["has_identity_proof"] and not signals.get("pan"):
        result.add(Finding(
            module="intake",
            code="MISSING_IDENTITY_PROOF",
            title="Identity document (PAN/Aadhaar) not provided",
            detail=(
                "Applicant PAN was declared but no identity proof document was uploaded "
                "and PAN could not be extracted from other files. Identity verification "
                "requires PAN/Aadhaar documentation."
            ),
            severity=Severity.medium,
            confidence=0.88,
            evidence={"applicant_pan": app_pan},
        ))

    if loan_type in ("home_loan", "loan_against_property") and not result.metrics["has_collateral_doc"]:
        result.add(Finding(
            module="intake",
            code="MISSING_COLLATERAL_DOC",
            title="Property / collateral documents missing",
            detail=(
                "Home loan and LAP applications require land title, sale deed, "
                "valuation report, or related collateral documents. None were identified "
                "in the uploaded pack."
            ),
            severity=Severity.high,
            confidence=0.92,
        ))

    if n_docs < 2 and loan >= 500_000:
        result.add(Finding(
            module="intake",
            code="INSUFFICIENT_DOCUMENT_COUNT",
            title="Document pack too thin for loan size",
            detail=(
                f"Only {n_docs} document(s) uploaded for a ₹{loan:,.0f} application. "
                "Underwriting integrity checks require a complete document set, not a "
                "single file."
            ),
            severity=Severity.high if loan >= 2_000_000 else Severity.medium,
            confidence=0.88,
        ))

    # ── OCR / relevance ─────────────────────────────────────────
    if n_docs > 0 and result.metrics["total_extracted_text"] < MIN_TEXT_CHARS:
        result.add(Finding(
            module="intake",
            code="UNREADABLE_DOCUMENTS",
            title="Uploaded documents contain insufficient extractable text",
            detail=(
                "OCR recovered almost no underwriting fields from the uploaded file(s). "
                "This may be an irrelevant image, blank scan, or non-document upload. "
                "Manual review is required."
            ),
            severity=Severity.high,
            confidence=0.85,
        ))

    if other_only and n_docs >= 1:
        result.add(Finding(
            module="intake",
            code="UNCLASSIFIED_DOCUMENTS",
            title="Documents not classified to a known underwriting type",
            detail=(
                "All uploaded files are marked 'Other'. Expected types include salary "
                "slip, bank statement, land title, Form 16, or ITR."
            ),
            severity=Severity.medium,
            confidence=0.8,
        ))

    if n_docs >= 1 and signal_count <= 1 and loan >= 300_000:
        result.add(Finding(
            module="intake",
            code="UNRELATED_DOCUMENT_CONTENT",
            title="Document content does not match underwriting requirements",
            detail=(
                "Uploaded file(s) lack PAN, monetary amounts, property identifiers, and "
                "dates typically present in loan documents. The pack appears unrelated "
                "or incomplete for this application."
            ),
            severity=Severity.high,
            confidence=0.8,
            evidence={"signals_found": signal_count},
        ))

    if financial_skipped and income > 0 and not result.metrics["has_bank_statement"]:
        result.add(Finding(
            module="intake",
            code="NO_FINANCIAL_VERIFICATION",
            title="Financial activity could not be verified",
            detail=(
                "No bank statement was available for transaction analysis. Declared "
                "income and payslip claims remain unverified."
            ),
            severity=Severity.high,
            confidence=0.9,
        ))

    doc_pans = [
        (d.get("extracted_fields") or {}).get("pan", "").upper()
        for d in documents
        if (d.get("extracted_fields") or {}).get("pan")
    ]
    if app_pan and doc_pans and all(p != app_pan for p in doc_pans):
        result.add(Finding(
            module="intake",
            code="PAN_MISMATCH_ACROSS_DOCS",
            title="PAN on documents does not match application",
            detail=f"Application PAN {app_pan} differs from PAN extracted from uploaded documents.",
            severity=Severity.high,
            confidence=0.85,
        ))

    block_auto_clear = any(
        f.code in {
            "MISSING_BANK_STATEMENT", "MISSING_COLLATERAL_DOC", "INSUFFICIENT_DOCUMENT_COUNT",
            "UNREADABLE_DOCUMENTS", "UNRELATED_DOCUMENT_CONTENT", "NO_FINANCIAL_VERIFICATION",
        }
        for f in result.findings
    )
    result.metrics["block_auto_clear"] = block_auto_clear
    result.metrics["evidence_sufficient"] = not block_auto_clear and n_docs >= 2

    result.compute_score()
    if block_auto_clear:
        result.score = max(result.score, 48.0)
    result.summary = (
        f"Intake review: {len(result.findings)} completeness issue(s) detected."
        if result.findings
        else f"Document pack appears complete ({n_docs} file(s))."
    )
    return result
