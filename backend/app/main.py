"""Forensiq AI — FastAPI application entrypoint."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import applications, cases, dashboard, policy, ws
from app.core.config import settings
from app.core.policy import load_persisted
from app.db.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.ensure_dirs()
    load_persisted()
    init_db()
    yield


app = FastAPI(
    title="Forensiq AI — Intelligent Document Integrity System",
    version=settings.app_version,
    description=(
        "Real-time underwriting integrity platform: document forensics, "
        "financial anomaly detection, cross-source verification, GIS/satellite "
        "validation and explainable risk intelligence."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(applications.router)
app.include_router(cases.router)
app.include_router(dashboard.router)
app.include_router(policy.router)
app.include_router(ws.router)

# Serve forensic artifacts (ELA heatmaps, copy-move overlays).
app.mount("/artifacts", StaticFiles(directory=str(settings.artifact_dir)), name="artifacts")


@app.get("/api/health", tags=["meta"])
def health() -> dict:
    return {
        "status": "ok",
        "app": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
    }
