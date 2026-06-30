"""Pydantic request / response schemas for the public API."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ApplicationCreate(BaseModel):
    applicant_name: str = Field(..., min_length=2, max_length=160)
    applicant_pan: str | None = None
    loan_type: str = "home_loan"
    loan_amount: float = 0.0
    declared_income: float = 0.0
    property_address: str | None = None
    property_lat: float | None = None
    property_lng: float | None = None


class DocumentOut(BaseModel):
    id: str
    doc_type: str
    filename: str
    mime_type: str
    size_bytes: int
    sha256: str | None
    integrity_score: float
    extracted_fields: dict[str, Any] | None
    forensics: dict[str, Any] | None
    artifacts: dict[str, Any] | None
    created_at: datetime

    class Config:
        from_attributes = True


class FindingOut(BaseModel):
    id: str
    module: str
    code: str
    title: str
    detail: str
    severity: str
    confidence: float
    evidence: dict[str, Any] | None
    created_at: datetime

    class Config:
        from_attributes = True


class AuditEventOut(BaseModel):
    id: str
    actor: str
    action: str
    detail: str | None
    created_at: datetime

    class Config:
        from_attributes = True


class CaseOut(BaseModel):
    id: str
    case_number: str
    status: str
    priority: str
    assignee: str | None
    summary: str | None
    resolution_note: str | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ApplicationSummary(BaseModel):
    id: str
    reference: str
    applicant_name: str
    loan_type: str
    loan_amount: float
    declared_income: float
    status: str
    risk_score: float
    risk_band: str | None
    recommendation: str | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ApplicationDetail(ApplicationSummary):
    applicant_pan: str | None
    property_address: str | None
    property_lat: float | None
    property_lng: float | None
    report: dict[str, Any] | None
    documents: list[DocumentOut] = []
    findings: list[FindingOut] = []
    events: list[AuditEventOut] = []
    case: CaseOut | None = None


class CaseUpdate(BaseModel):
    status: str | None = None
    assignee: str | None = None
    resolution_note: str | None = None


class DecisionUpdate(BaseModel):
    decision: str  # approved | declined | manual_review
    note: str | None = None
    actor: str = "underwriter"


class DashboardStats(BaseModel):
    total_applications: int
    analyzing: int
    auto_cleared: int
    manual_review: int
    escalated: int
    open_cases: int
    avg_risk_score: float
    fraud_prevented_value: float
    risk_distribution: dict[str, int]
    total_findings: int
    high_severity_findings: int
    pending_analysis: int
    recent: list[ApplicationSummary]
