"""Upload validation helpers."""
from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException, UploadFile

from app.core.config import settings

ALLOWED_EXTENSIONS = frozenset({
    ".pdf", ".jpg", ".jpeg", ".png", ".csv", ".txt", ".tif", ".tiff", ".webp",
})
ALLOWED_MIME_PREFIXES = (
    "image/",
    "application/pdf",
    "text/csv",
    "text/plain",
    "application/csv",
    "application/octet-stream",
)


def validate_upload_meta(filename: str, mime_type: str | None) -> None:
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            400,
            f"File type '{ext or 'unknown'}' is not allowed. "
            f"Accepted: PDF, images, CSV bank statements.",
        )
    mime = (mime_type or "").lower()
    if mime and not any(mime.startswith(p) if p.endswith("/") else mime == p for p in ALLOWED_MIME_PREFIXES):
        raise HTTPException(400, f"MIME type '{mime}' is not allowed for uploads.")


def save_upload_limited(uf: UploadFile, target: Path) -> int:
    """Stream upload to disk; enforce size limit."""
    written = 0
    max_bytes = settings.max_upload_bytes
    try:
        with target.open("wb") as out:
            while True:
                chunk = uf.file.read(65536)
                if not chunk:
                    break
                written += len(chunk)
                if written > max_bytes:
                    raise HTTPException(
                        413,
                        f"File exceeds maximum upload size of {max_bytes // (1024 * 1024)} MB.",
                    )
                out.write(chunk)
    except HTTPException:
        target.unlink(missing_ok=True)
        raise
    return written
