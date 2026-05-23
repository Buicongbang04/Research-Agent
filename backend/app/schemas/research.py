"""Research request/response schemas."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.db.models import ReportStatus


class ResearchCreate(BaseModel):
    prompt: str = Field(min_length=4, max_length=2000)


class ReportOut(BaseModel):
    id: uuid.UUID
    status: ReportStatus
    prompt: str
    result_md: str | None = None
    extra: dict[str, Any] | None = None  # column "metadata" in DB; exposed as "extra" in API
    error: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ReportSummary(BaseModel):
    id: uuid.UUID
    status: ReportStatus
    prompt: str
    created_at: datetime

    model_config = {"from_attributes": True}
