"""Shared primitives used across all analysis engines.

Every engine returns a uniform ``ModuleResult`` so the risk aggregator and the
real-time pipeline can treat them generically. This keeps the architecture
extensible — adding a new detector never requires changing the orchestrator.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any


class Severity(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"

    @property
    def rank(self) -> int:
        return {"low": 1, "medium": 2, "high": 3, "critical": 4}[self.value]


# Per-severity contribution toward a 0-100 module risk score.
SEVERITY_WEIGHT: dict[Severity, float] = {
    Severity.low: 8.0,
    Severity.medium: 22.0,
    Severity.high: 45.0,
    Severity.critical: 80.0,
}


@dataclass
class Finding:
    """A single explainable red flag with supporting evidence."""

    module: str
    code: str
    title: str
    detail: str
    severity: Severity
    confidence: float = 0.6  # 0-1
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["severity"] = self.severity.value
        return d


@dataclass
class ModuleResult:
    """Output of a single analysis module."""

    module: str
    score: float = 0.0                       # 0 (clean) → 100 (high risk)
    summary: str = ""
    findings: list[Finding] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    artifacts: dict[str, str] = field(default_factory=dict)
    status: str = "ok"                       # ok | skipped | error

    def add(self, finding: Finding) -> None:
        self.findings.append(finding)

    def compute_score(self) -> float:
        """Aggregate findings into a 0-100 score using a saturating model.

        Multiple independent flags compound, but we use a diminishing-returns
        curve so a single critical finding dominates while many minor flags
        still accumulate meaningfully — and the score can never exceed 100.
        """
        residual = 1.0
        for f in self.findings:
            contribution = SEVERITY_WEIGHT[f.severity] * max(0.05, min(1.0, f.confidence))
            residual *= (1.0 - contribution / 100.0)
        self.score = round((1.0 - residual) * 100.0, 2)
        return self.score

    def to_dict(self) -> dict[str, Any]:
        return {
            "module": self.module,
            "score": self.score,
            "summary": self.summary,
            "status": self.status,
            "metrics": self.metrics,
            "artifacts": self.artifacts,
            "findings": [f.to_dict() for f in self.findings],
        }


def band_for_score(score: float) -> str:
    if score >= 75:
        return "critical"
    if score >= 60:
        return "high"
    if score >= 30:
        return "medium"
    return "low"
