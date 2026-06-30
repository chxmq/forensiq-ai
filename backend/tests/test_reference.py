"""Reference numbering and upload validation."""
from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.api.applications import _reference
from app.core.uploads import validate_upload_meta


def test_reference_uses_max_not_count():
    db = MagicMock()
    db.query.return_value.filter.return_value.order_by.return_value.first.return_value = (
        f"APP-{datetime.now(timezone.utc).year}-00007",
    )
    ref = _reference(db)
    assert ref.endswith("00008")


def test_reject_unknown_extension():
    with pytest.raises(HTTPException) as exc:
        validate_upload_meta("malware.exe", "application/octet-stream")
    assert exc.value.status_code == 400


def test_allow_pdf():
    validate_upload_meta("deed.pdf", "application/pdf")
