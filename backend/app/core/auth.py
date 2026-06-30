"""Session tokens for underwriter API / WebSocket access."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Annotated

from fastapi import Depends, HTTPException, Query, WebSocketException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import get_settings

_bearer = HTTPBearer(auto_error=False)
TOKEN_TTL_SECONDS = 60 * 60 * 24 * 7  # 7 days


def _sign(body: str) -> str:
    return hmac.new(
        get_settings().auth_secret.encode(),
        body.encode(),
        hashlib.sha256,
    ).hexdigest()


def create_access_token(username: str) -> str:
    payload = {"sub": username, "exp": int(time.time()) + TOKEN_TTL_SECONDS}
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()
    return f"{body}.{_sign(body)}"


def verify_access_token(token: str | None) -> str:
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentication required")
    try:
        body, sig = token.rsplit(".", 1)
    except ValueError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token") from exc
    if not hmac.compare_digest(_sign(body), sig):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")
    try:
        payload = json.loads(base64.urlsafe_b64decode(body.encode()))
    except (json.JSONDecodeError, ValueError) as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token") from exc
    if int(payload.get("exp", 0)) < int(time.time()):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token expired")
    username = payload.get("sub")
    if not username:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")
    return str(username)


def verify_ws_token(token: str | None) -> str:
    try:
        return verify_access_token(token)
    except HTTPException as exc:
        raise WebSocketException(code=1008, reason=exc.detail) from exc


def authenticate_user(username: str, password: str) -> bool:
    return (
        hmac.compare_digest(username, get_settings().auth_username)
        and hmac.compare_digest(password, get_settings().auth_password)
    )


def _resolve_token(
    credentials: HTTPAuthorizationCredentials | None,
    token_query: str | None,
) -> str | None:
    if credentials and credentials.credentials:
        return credentials.credentials
    return token_query


def require_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)] = None,
    token: Annotated[str | None, Query(alias="token")] = None,
) -> str:
    if not get_settings().auth_enabled:
        return "guest"
    return verify_access_token(_resolve_token(credentials, token))


CurrentUser = Annotated[str, Depends(require_user)]
