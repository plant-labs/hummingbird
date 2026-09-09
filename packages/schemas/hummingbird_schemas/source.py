from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl

from .enums import SourceType


class SourceCreate(BaseModel):
    url: HttpUrl
    outlet: str = Field(..., min_length=1, max_length=256)
    source_type: SourceType
    fetched_at: datetime
    raw_ref: Optional[str] = None
    reliability_tier: int = Field(default=3, ge=1, le=5)
    excerpt: Optional[str] = None
    published_at: Optional[datetime] = None


class SourceRecord(SourceCreate):
    source_id: UUID
