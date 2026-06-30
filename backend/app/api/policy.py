"""Policy configuration API."""
from __future__ import annotations

from fastapi import APIRouter

from app.core.auth import CurrentUser
from app.core.policy import read_policy, update_policy
from app.data.document_types import CANARA_DOCUMENT_TYPES

router = APIRouter(prefix="/api", tags=["policy"])


@router.get("/config")
def get_config(_user: CurrentUser) -> dict:
    return read_policy()


@router.patch("/config")
def patch_config(payload: dict, user: CurrentUser) -> dict:
    updated = update_policy(payload)
    updated["_updated_by"] = user
    return updated


@router.get("/document-types")
def document_types(_user: CurrentUser) -> list[dict[str, str]]:
    return CANARA_DOCUMENT_TYPES
