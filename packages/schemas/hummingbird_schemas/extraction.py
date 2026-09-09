"""LLM extraction schemas — extraction only, never free generation."""

from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, Field, model_validator

from .enums import EventType, IncidentStatus, LocationPrecision, SourceType


class BronzePayload(BaseModel):
    """Immutable raw ingest record landed in bronze."""

    content_hash: str
    source_type: SourceType
    fetched_at: datetime
    ingest_run_id: str
    url: Optional[str] = None
    outlet: Optional[str] = None
    title: Optional[str] = None
    body: Optional[str] = None
    payload: dict[str, Any] = Field(default_factory=dict)


class ExtractedField(BaseModel):
    field_name: str
    value: Any
    source_span: str = Field(..., min_length=1)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def span_must_be_nonempty(self) -> "ExtractedField":
        if not self.source_span.strip():
            raise ValueError("source_span is required; no invented facts")
        return self


class ExtractionResult(BaseModel):
    """Constrained LLM output: only facts grounded in source text."""

    event_type: EventType
    date_occurred: Optional[date] = None
    date_reported: Optional[date] = None
    state: Optional[str] = None
    lga: Optional[str] = None
    location_precision: LocationPrecision = LocationPrecision.STATE
    current_status: IncidentStatus = IncidentStatus.ONGOING
    headline: Optional[str] = None
    fields: list[ExtractedField] = Field(default_factory=list)
    source_text_hash: str
    rejected: bool = False
    reject_reason: Optional[str] = None
