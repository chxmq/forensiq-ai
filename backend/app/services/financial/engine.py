"""Financial integrity & anomaly analysis.

Combines forensic-accounting and ML techniques:

* **Benford's Law** — genuine, organically-generated financial figures follow a
  logarithmic first-digit distribution. Fabricated/edited statements usually
  violate it; we test with a chi-square goodness-of-fit.
* **Isolation Forest** — unsupervised outlier detection over transaction
  features to surface anomalous / injected transactions.
* **Income consistency** — reconciles *declared* income against the income the
  transaction activity actually supports (a core underwriting check).
* **Synthetic-pattern detection** — round-number bias, repeated identical
  amounts and unnaturally regular timing that betray fabricated statements.
"""
from __future__ import annotations

import math
from collections import Counter
from datetime import datetime
from typing import Any

import numpy as np

from app.core.config import settings
from app.services.common import Finding, ModuleResult, Severity

BENFORD = {d: math.log10(1 + 1 / d) for d in range(1, 10)}


def _parse_date(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(str(value)[:10], fmt)
        except ValueError:
            continue
    return None


def _first_digit(x: float) -> int | None:
    x = abs(x)
    if x < 1:
        return None
    return int(str(int(x))[0])


def benford_test(amounts: list[float]) -> tuple[dict[str, Any], Finding | None]:
    digits = [d for a in amounts if (d := _first_digit(a))]
    n = len(digits)
    if n < 40:
        return {"benford_n": n, "benford_applicable": False}, None

    counts = Counter(digits)
    observed = {d: counts.get(d, 0) / n for d in range(1, 10)}
    chi2 = sum(((counts.get(d, 0) - BENFORD[d] * n) ** 2) / (BENFORD[d] * n) for d in range(1, 10))
    mad = sum(abs(observed[d] - BENFORD[d]) for d in range(1, 10)) / 9

    metrics = {
        "benford_n": n,
        "benford_applicable": True,
        "benford_chi2": round(chi2, 2),
        "benford_mad": round(mad, 4),
        "benford_observed": {str(d): round(observed[d], 4) for d in range(1, 10)},
        "benford_expected": {str(d): round(BENFORD[d], 4) for d in range(1, 10)},
    }

    if chi2 > settings.benford_chi2_critical:
        sev = Severity.high if chi2 > settings.benford_chi2_critical * 2 else Severity.medium
        finding = Finding(
            module="financial",
            code="BENFORD_VIOLATION",
            title="Financial figures violate Benford's Law",
            detail=(
                f"First-digit distribution across {n} monetary values deviates "
                f"significantly from Benford's Law (χ²={chi2:.1f}, critical="
                f"{settings.benford_chi2_critical}). Naturally-occurring financial "
                "data follows this law; large deviations are a strong indicator of "
                "fabricated or manually-edited figures."
            ),
            severity=sev,
            confidence=min(0.9, 0.5 + chi2 / 100),
            evidence={"chi2": round(chi2, 2), "mad": round(mad, 4),
                      "observed": metrics["benford_observed"],
                      "expected": metrics["benford_expected"]},
        )
        return metrics, finding
    return metrics, None


def isolation_forest_anomalies(txns: list[dict]) -> tuple[dict[str, Any], Finding | None]:
    rows = []
    for t in txns:
        amt = float(t.get("amount", 0) or 0)
        dt = _parse_date(t.get("date"))
        rows.append([
            abs(amt),
            math.log1p(abs(amt)),
            1.0 if amt < 0 else 0.0,
            dt.weekday() if dt else 0,
            dt.day if dt else 1,
        ])
    if len(rows) < 30:
        return {"iforest_applicable": False, "iforest_n": len(rows)}, None

    from sklearn.ensemble import IsolationForest

    X = np.array(rows, dtype=float)
    model = IsolationForest(n_estimators=200, contamination="auto", random_state=42)
    preds = model.fit_predict(X)
    scores = model.score_samples(X)
    anomaly_idx = [i for i, p in enumerate(preds) if p == -1]
    ratio = len(anomaly_idx) / len(rows)

    top = sorted(anomaly_idx, key=lambda i: scores[i])[:6]
    examples = [
        {
            "date": str(txns[i].get("date")),
            "amount": float(txns[i].get("amount", 0) or 0),
            "description": str(txns[i].get("description", "")),
            "anomaly_score": round(float(scores[i]), 3),
        }
        for i in top
    ]

    metrics = {
        "iforest_applicable": True,
        "iforest_n": len(rows),
        "iforest_anomalies": len(anomaly_idx),
        "iforest_anomaly_ratio": round(ratio, 3),
        "iforest_examples": examples,
    }

    if ratio > 0.28:
        sev = Severity.high if ratio > 0.45 else Severity.medium
        finding = Finding(
            module="financial",
            code="TXN_ANOMALY_CLUSTER",
            title="Unusual cluster of anomalous transactions",
            detail=(
                f"{len(anomaly_idx)} of {len(rows)} transactions ({ratio*100:.1f}%) were "
                "flagged as statistical outliers by an Isolation Forest model. A high "
                "anomaly rate suggests injected or fabricated transactions rather than "
                "organic account activity."
            ),
            severity=sev,
            confidence=min(0.85, 0.45 + ratio),
            evidence={"anomaly_ratio": round(ratio, 3), "examples": examples},
        )
        return metrics, finding
    return metrics, None


def synthetic_pattern_test(txns: list[dict]) -> tuple[dict[str, Any], list[Finding]]:
    findings: list[Finding] = []
    amounts = [abs(float(t.get("amount", 0) or 0)) for t in txns if t.get("amount")]
    metrics: dict[str, Any] = {}
    if len(amounts) < 20:
        return metrics, findings

    round_ratio = sum(1 for a in amounts if a >= 1000 and a % 1000 == 0) / len(amounts)
    metrics["round_amount_ratio"] = round(round_ratio, 3)
    if round_ratio > 0.45:
        findings.append(
            Finding(
                module="financial",
                code="ROUND_NUMBER_BIAS",
                title="Excessive round-number transactions",
                detail=(
                    f"{round_ratio*100:.0f}% of transactions are exact multiples of 1,000. "
                    "Real-world activity rarely produces so many round figures; this is "
                    "typical of manually fabricated statements."
                ),
                severity=Severity.medium,
                confidence=min(0.8, round_ratio),
                evidence={"round_ratio": round(round_ratio, 3)},
            )
        )

    counts = Counter(round(a, 2) for a in amounts)
    most_amt, most_n = counts.most_common(1)[0]
    dup_ratio = most_n / len(amounts)
    metrics["duplicate_amount_ratio"] = round(dup_ratio, 3)
    if dup_ratio > 0.3 and most_n >= 6:
        findings.append(
            Finding(
                module="financial",
                code="REPEATED_AMOUNT",
                title="Repeated identical transaction amounts",
                detail=(
                    f"The amount {most_amt:,.2f} repeats {most_n} times "
                    f"({dup_ratio*100:.0f}% of transactions), an unnatural concentration "
                    "indicative of copied/fabricated entries."
                ),
                severity=Severity.medium,
                confidence=min(0.75, dup_ratio),
                evidence={"amount": most_amt, "occurrences": most_n},
            )
        )

    # Timing regularity.
    dates = sorted(d for t in txns if (d := _parse_date(t.get("date"))))
    if len(dates) > 15:
        gaps = np.array([(dates[i + 1] - dates[i]).days for i in range(len(dates) - 1)], dtype=float)
        if gaps.mean() > 0:
            cv = float(gaps.std() / (gaps.mean() + 1e-6))
            metrics["interval_cv"] = round(cv, 3)
            if cv < 0.15:
                findings.append(
                    Finding(
                        module="financial",
                        code="REGULAR_TIMING",
                        title="Unnaturally regular transaction timing",
                        detail=(
                            "Inter-transaction intervals are almost perfectly uniform "
                            f"(coefficient of variation {cv:.2f}). Genuine account activity "
                            "is irregular; near-constant spacing suggests auto-generated data."
                        ),
                        severity=Severity.low,
                        confidence=0.6,
                        evidence={"interval_cv": round(cv, 3)},
                    )
                )
    return metrics, findings


def income_consistency(txns: list[dict], declared_income: float, loan_amount: float) -> tuple[dict[str, Any], list[Finding]]:
    findings: list[Finding] = []
    metrics: dict[str, Any] = {}
    if not txns:
        return metrics, findings

    credits = [float(t.get("amount", 0) or 0) for t in txns if float(t.get("amount", 0) or 0) > 0]
    dates = sorted(d for t in txns if (d := _parse_date(t.get("date"))))
    if not credits or len(dates) < 2:
        return metrics, findings

    span_days = max(1, (dates[-1] - dates[0]).days)
    months = max(1.0, span_days / 30.4)
    total_credit = sum(credits)
    implied_annual = total_credit / months * 12
    metrics["observed_annual_inflow"] = round(implied_annual, 2)
    metrics["declared_income"] = declared_income

    if declared_income > 0 and implied_annual > 0:
        ratio = declared_income / implied_annual
        metrics["income_to_inflow_ratio"] = round(ratio, 2)
        if ratio > 1.8:
            sev = Severity.high if ratio > 3 else Severity.medium
            findings.append(
                Finding(
                    module="financial",
                    code="INCOME_OVERSTATEMENT",
                    title="Declared income not supported by transaction activity",
                    detail=(
                        f"Declared annual income is ₹{declared_income:,.0f}, but observed "
                        f"account inflows imply only ₹{implied_annual:,.0f}/yr "
                        f"({ratio:.1f}× overstatement). The income narrative is not "
                        "corroborated by actual cash flow."
                    ),
                    severity=sev,
                    confidence=min(0.85, 0.4 + ratio / 8),
                    evidence={"declared": declared_income, "observed": round(implied_annual)},
                )
            )

    if loan_amount > 0 and implied_annual > 0:
        dti = loan_amount / implied_annual
        metrics["loan_to_income_multiple"] = round(dti, 2)
        if dti > 12:
            findings.append(
                Finding(
                    module="financial",
                    code="HIGH_LOAN_MULTIPLE",
                    title="Loan amount very high relative to verified income",
                    detail=(
                        f"Requested loan (₹{loan_amount:,.0f}) is {dti:.1f}× verified annual "
                        "inflow, an elevated leverage ratio that warrants scrutiny."
                    ),
                    severity=Severity.medium,
                    confidence=0.6,
                    evidence={"loan": loan_amount, "verified_income": round(implied_annual)},
                )
            )
    return metrics, findings


def payslip_statement_reconciliation(
    txns: list[dict],
    document_fields: list[dict[str, Any]],
    declared_income: float,
) -> tuple[dict[str, Any], list[Finding]]:
    """Cross-check payslip/Form 16/ITR figures against bank salary credits."""
    metrics: dict[str, Any] = {}
    findings: list[Finding] = []

    payslip_gross = 0.0
    payslip_net = 0.0
    payslip_monthly = 0.0
    source_doc = None
    for doc in document_fields:
        dtype = doc.get("doc_type") or ""
        fields = doc.get("fields") or {}
        if dtype not in {"salary_slip", "form_16", "itr", "income_certificate"}:
            continue
        source_doc = doc.get("filename") or dtype
        payslip_gross = max(payslip_gross, float(fields.get("gross_salary") or 0))
        payslip_net = max(payslip_net, float(fields.get("net_salary") or 0))
        payslip_monthly = max(payslip_monthly, float(fields.get("monthly_salary") or 0))
        if not payslip_gross and fields.get("max_amount"):
            payslip_gross = float(fields["max_amount"])

    if payslip_monthly and not payslip_gross:
        payslip_gross = payslip_monthly * 12
    if payslip_net and not payslip_gross:
        payslip_gross = payslip_net * 12

    if payslip_gross <= 0 and declared_income <= 0:
        return {"payslip_check_applicable": False}, findings

    metrics["payslip_check_applicable"] = True
    metrics["payslip_gross_annual"] = round(payslip_gross, 2) if payslip_gross else None
    metrics["payslip_net_annual"] = round(payslip_net * 12, 2) if payslip_net else None
    metrics["payslip_source_document"] = source_doc

    credits = [
        float(t.get("amount", 0) or 0)
        for t in txns
        if float(t.get("amount", 0) or 0) > 0
        and any(k in str(t.get("description", "")).lower() for k in ("salary", "payroll", "credit", "neft", "imps"))
    ]
    if not credits:
        credits = [float(t.get("amount", 0) or 0) for t in txns if float(t.get("amount", 0) or 0) > 0]

    if not credits:
        return metrics, findings

    avg_credit = float(np.mean(credits))
    annual_from_bank = avg_credit * 12
    metrics["avg_monthly_bank_credit"] = round(avg_credit, 2)
    metrics["annualized_bank_credits"] = round(annual_from_bank, 2)

    reference_income = payslip_gross or declared_income
    if reference_income <= 0:
        return metrics, findings

    ratio = annual_from_bank / reference_income if reference_income else 0
    metrics["payslip_to_bank_ratio"] = round(ratio, 2)

    if ratio < 0.45:
        findings.append(
            Finding(
                module="financial",
                code="PAYSLIP_BANK_MISMATCH",
                title="Salary slip income not supported by bank credits",
                detail=(
                    f"Document-derived annual income is ₹{reference_income:,.0f} "
                    f"(from {source_doc or 'application'}), but bank salary credits "
                    f"annualize to only ₹{annual_from_bank:,.0f} ({ratio:.0%} of claimed). "
                    "This is a core Canara underwriting check — payslip verification "
                    "against bank statement activity."
                ),
                severity=Severity.high if ratio < 0.3 else Severity.medium,
                confidence=0.82,
                evidence={
                    "payslip_gross": payslip_gross,
                    "annual_from_bank": round(annual_from_bank, 2),
                    "ratio": round(ratio, 2),
                    "source_document": source_doc,
                },
            )
        )
    elif payslip_gross and declared_income > 0 and payslip_gross < declared_income * 0.6:
        findings.append(
            Finding(
                module="financial",
                code="PAYSLIP_DECLARED_MISMATCH",
                title="Declared income exceeds payslip / Form 16",
                detail=(
                    f"Applicant declared ₹{declared_income:,.0f} annual income but "
                    f"supporting income document ({source_doc}) shows "
                    f"₹{payslip_gross:,.0f}. Material overstatement detected."
                ),
                severity=Severity.high,
                confidence=0.78,
                evidence={
                    "declared_income": declared_income,
                    "document_income": payslip_gross,
                },
            )
        )

    return metrics, findings


def analyze_financials(
    txns: list[dict],
    declared_income: float = 0.0,
    loan_amount: float = 0.0,
    document_fields: list[dict[str, Any]] | None = None,
) -> ModuleResult:
    result = ModuleResult(module="financial")
    if not txns:
        result.status = "skipped"
        result.summary = "No transaction data available for financial analysis."
        return result

    amounts = [abs(float(t.get("amount", 0) or 0)) for t in txns if t.get("amount")]

    bm, bf = benford_test(amounts)
    result.metrics.update(bm)
    if bf:
        result.add(bf)

    im, ifd = isolation_forest_anomalies(txns)
    result.metrics.update(im)
    if ifd:
        result.add(ifd)

    sm, sfs = synthetic_pattern_test(txns)
    result.metrics.update(sm)
    for f in sfs:
        result.add(f)

    cm, cfs = income_consistency(txns, declared_income, loan_amount)
    result.metrics.update(cm)
    for f in cfs:
        result.add(f)

    pm, pfs = payslip_statement_reconciliation(txns, document_fields or [], declared_income)
    result.metrics.update(pm)
    for f in pfs:
        result.add(f)

    result.metrics["transaction_count"] = len(txns)
    result.compute_score()
    result.summary = (
        f"Analyzed {len(txns)} transactions; {len(result.findings)} financial "
        f"integrity issue(s) detected." if result.findings
        else f"Analyzed {len(txns)} transactions; financial activity appears consistent."
    )
    return result
