"""First-run bootstrap: create dirs, init DB, seed demo data if empty."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import settings  # noqa: E402
from app.core.policy import load_persisted  # noqa: E402
from app.db import models  # noqa: E402
from app.db.database import SessionLocal, init_db  # noqa: E402


def main() -> None:
    settings.ensure_dirs()
    load_persisted()
    init_db()

    db = SessionLocal()
    try:
        has_apps = db.query(models.Application).count() > 0
    finally:
        db.close()

    if has_apps:
        print("• Database already seeded — skipping demo reset.")
        return

    print("• Empty database — seeding demo applications (first run)...")

    from scripts.seed import main as seed_main  # noqa: WPS433

    asyncio.run(seed_main())


if __name__ == "__main__":
    main()
