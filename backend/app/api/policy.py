"""Policy configuration API."""
from __future__ import annotations

from fastapi import APIRouter

from app.core.policy import read_policy, update_policy
from app.data.document_types import CANARA_DOCUMENT_TYPES

router = APIRouter(prefix="/api", tags=["policy"])


@router.get("/config")
def get_config() -> dict:
    return read_policy()


@router.patch("/config")
def patch_config(payload: dict) -> dict:
    return update_policy(payload)


@router.get("/document-types")
def document_types() -> list[dict[str, str]]:
    return CANARA_DOCUMENT_TYPES
