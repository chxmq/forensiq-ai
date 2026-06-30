"""Forensiq AI backend tests."""
from __future__ import annotations

import os

# Disable auth for API tests unless a test overrides it.
os.environ.setdefault("FORENSIQ_AUTH_ENABLED", "false")
