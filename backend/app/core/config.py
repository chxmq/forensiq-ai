"""Application configuration.

Centralised, environment-overridable settings for the Forensiq AI backend.
All tunable thresholds for the forensic / risk engines live here so the
behaviour of the platform is transparent and auditable.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent  # .../backend/app
BACKEND_DIR = BASE_DIR.parent                       # .../backend


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FORENSIQ_", env_file=".env", extra="ignore")

    # ── Meta ────────────────────────────────────────────────────
    app_name: str = "Forensiq AI"
    app_version: str = "1.0.0"
    environment: str = "development"

    # ── Storage ─────────────────────────────────────────────────
    storage_dir: Path = BACKEND_DIR / "storage"
    upload_dir: Path = BACKEND_DIR / "storage" / "uploads"
    artifact_dir: Path = BACKEND_DIR / "storage" / "artifacts"
    data_dir: Path = BASE_DIR / "data"

    # ── Database ────────────────────────────────────────────────
    database_url: str = f"sqlite:///{BACKEND_DIR / 'forensiq.db'}"

    # ── Frontend (production: FastAPI serves built Vite app) ────
    static_dir: Path | None = None

    # ── CORS ────────────────────────────────────────────────────
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # ── Risk engine weights (must sum ~1.0) ─────────────────────
    weight_document: float = 0.25
    weight_financial: float = 0.20
    weight_verification: float = 0.20
    weight_gis: float = 0.15
    weight_intake: float = 0.20

    # ── Decision thresholds (0-100 risk scale) ──────────────────
    threshold_approve: float = 30.0     # below → auto-approve eligible
    threshold_review: float = 60.0      # below → manual review
    threshold_escalate: float = 75.0    # at/above → auto-escalate (decline track)

    # ── Forensic detector thresholds ────────────────────────────
    ela_quality: int = 90               # JPEG re-save quality for ELA
    ela_suspicious_ratio: float = 0.020 # fraction of high-error pixels → suspicious
    copymove_min_matches: int = 12      # min ORB matches to flag copy-move
    benford_chi2_critical: float = 15.51  # χ² critical value, 8 dof, p<0.05

    def ensure_dirs(self) -> None:
        for d in (self.storage_dir, self.upload_dir, self.artifact_dir):
            d.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    s.ensure_dirs()
    return s


settings = get_settings()
