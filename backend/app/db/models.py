"""Relational models for applications, documents, findings and audit trail."""
from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


def _uuid() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(timezone.utc)


class RiskBand(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class ApplicationStatus(str, enum.Enum):
    draft = "draft"
    analyzing = "analyzing"
    analyzed = "analyzed"
    failed = "failed"
    auto_cleared = "auto_cleared"
    manual_review = "manual_review"
    escalated = "escalated"
    approved = "approved"
    declined = "declined"


class CaseStatus(str, enum.Enum):
    open = "open"
    investigating = "investigating"
    resolved_clear = "resolved_clear"
    resolved_fraud = "resolved_fraud"


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    reference: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    applicant_name: Mapped[str] = mapped_column(String(160))
    applicant_pan: Mapped[str | None] = mapped_column(String(20), nullable=True)
    loan_type: Mapped[str] = mapped_column(String(64), default="home_loan")
    loan_amount: Mapped[float] = mapped_column(Float, default=0.0)
    declared_income: Mapped[float] = mapped_column(Float, default=0.0)
    property_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    property_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    property_lng: Mapped[float | None] = mapped_column(Float, nullable=True)

    status: Mapped[ApplicationStatus] = mapped_column(
        Enum(ApplicationStatus), default=ApplicationStatus.draft, index=True
    )
    risk_score: Mapped[float] = mapped_column(Float, default=0.0)
    risk_band: Mapped[RiskBand | None] = mapped_column(Enum(RiskBand), nullable=True)
    recommendation: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Full structured risk report (per-module scores, contradictions, reasoning)
    report: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )

    documents: Mapped[list["Document"]] = relationship(
        back_populates="application", cascade="all, delete-orphan"
    )
    findings: Mapped[list["Finding"]] = relationship(
        back_populates="application", cascade="all, delete-orphan"
    )
    events: Mapped[list["AuditEvent"]] = relationship(
        back_populates="application", cascade="all, delete-orphan"
    )
    case: Mapped["Case | None"] = relationship(
        back_populates="application", uselist=False, cascade="all, delete-orphan"
    )


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.id"), index=True)
    doc_type: Mapped[str] = mapped_column(String(64), default="unknown")
    filename: Mapped[str] = mapped_column(String(255))
    stored_path: Mapped[str] = mapped_column(String(512))
    mime_type: Mapped[str] = mapped_column(String(120), default="application/octet-stream")
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)

    integrity_score: Mapped[float] = mapped_column(Float, default=0.0)  # 0=clean,100=tampered
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    extracted_fields: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    forensics: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    artifacts: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # paths to heatmaps etc.

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    application: Mapped["Application"] = relationship(back_populates="documents")


class Finding(Base):
    """An individual evidence item / red flag surfaced by any engine."""

    __tablename__ = "findings"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.id"), index=True)
    module: Mapped[str] = mapped_column(String(48), index=True)  # forensics/financial/...
    code: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(200))
    detail: Mapped[str] = mapped_column(Text)
    severity: Mapped[RiskBand] = mapped_column(Enum(RiskBand))
    confidence: Mapped[float] = mapped_column(Float, default=0.0)  # 0-1
    evidence: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    application: Mapped["Application"] = relationship(back_populates="findings")


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.id"), index=True)
    actor: Mapped[str] = mapped_column(String(80), default="system")
    action: Mapped[str] = mapped_column(String(120))
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    application: Mapped["Application"] = relationship(back_populates="events")


class Case(Base):
    __tablename__ = "cases"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.id"), unique=True, index=True)
    case_number: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    status: Mapped[CaseStatus] = mapped_column(Enum(CaseStatus), default=CaseStatus.open, index=True)
    priority: Mapped[RiskBand] = mapped_column(Enum(RiskBand), default=RiskBand.high)
    assignee: Mapped[str | None] = mapped_column(String(80), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolution_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )

    application: Mapped["Application"] = relationship(back_populates="case")
