"""Authenticated access to forensic artifact images."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.core.auth import CurrentUser
from app.core.config import settings

router = APIRouter(prefix="/api/artifacts", tags=["artifacts"])

_MEDIA_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}


@router.get("/{filename}")
def get_artifact(filename: str, _user: CurrentUser) -> FileResponse:
    safe = Path(filename).name
    if safe != filename or ".." in filename:
        raise HTTPException(404, "Artifact not found")
    path = (settings.artifact_dir / safe).resolve()
    root = settings.artifact_dir.resolve()
    if not path.is_file() or root not in path.parents:
        raise HTTPException(404, "Artifact not found")
    media = _MEDIA_TYPES.get(path.suffix.lower(), "application/octet-stream")
    return FileResponse(path, media_type=media)
