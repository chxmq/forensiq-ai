"""Underwriter authentication."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.auth import authenticate_user, create_access_token
from app.core.config import get_settings

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=80)
    password: str = Field(..., min_length=4, max_length=120)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    auth_enabled: bool


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest) -> LoginResponse:
    if not get_settings().auth_enabled:
        return LoginResponse(
            access_token=create_access_token(payload.username or "guest"),
            username=payload.username or "guest",
            auth_enabled=False,
        )
    if not authenticate_user(payload.username, payload.password):
        raise HTTPException(401, "Invalid username or password")
    return LoginResponse(
        access_token=create_access_token(payload.username),
        username=payload.username,
        auth_enabled=True,
    )


@router.get("/status")
def auth_status() -> dict:
    return {
        "auth_enabled": get_settings().auth_enabled,
        "username_hint": get_settings().auth_username if get_settings().auth_enabled else None,
    }
