from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

REPORT_CATEGORIES = ("sexual", "minor", "violence", "hate", "other")
SOURCE_SERVER = "server"
SOURCE_DEVICE = "device"
SOURCE_NONE = "none"
MAX_NOTE_CHARS = 500


@dataclass(frozen=True)
class Report:
    id: str
    reporter_id: str
    job_id: str
    category: str
    note: str
    image_source: str
    image_name: Optional[str]
    created_at: datetime
    resolved_at: Optional[datetime] = None
    outcome: Optional[str] = None
