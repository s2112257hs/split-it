from __future__ import annotations

import os


class Config:
    DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
    RECEIPT_OWNER_ID = os.getenv("RECEIPT_OWNER_ID", "mvp-owner")
