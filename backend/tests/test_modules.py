"""Module-level analysis behaviour."""
from __future__ import annotations

from app.services.common import Severity
from app.services.financial.engine import analyze_financials
from app.services.gis.engine import analyze_gis


def test_financial_skip_emits_finding():
    result = analyze_financials([], declared_income=1_000_000)
    assert result.status == "skipped"
    assert any(f.code == "NO_BANK_STATEMENT_DATA" for f in result.findings)
    assert result.findings[0].severity == Severity.high


def test_gis_skip_emits_finding():
    result = analyze_gis(
        {"property_address": "Unknown Place, Nowhere 000000"},
        {},
    )
    assert result.status == "skipped"
    assert any(f.code in ("PARCEL_NOT_LOCATED", "SATELLITE_OBSERVATION_UNAVAILABLE") for f in result.findings)
