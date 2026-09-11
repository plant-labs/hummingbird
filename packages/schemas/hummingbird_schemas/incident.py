from datetime import date, datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from .enums import (
    EventType,
    IncidentStatus,
    LocationPrecision,
    SourceRole,
    VerificationStatus,
)
from .source import SourceRecord


class CitedField(BaseModel):
    """Every published fact must carry a source citation."""

    field_name: str
    value: Any
    source_id: UUID
    source_span: str = Field(
        ...,
        description="Verbatim excerpt from the source that supports this field",
        min_length=1,
    )
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class StatusHistoryEntry(BaseModel):
    from_status: Optional[IncidentStatus] = None
    to_status: IncidentStatus
    changed_at: datetime
    source_id: UUID
    note: Optional[str] = None


class IncidentCreate(BaseModel):
    event_type: EventType
    date_occurred: Optional[date] = None
    date_reported: date
    state: str
    lga: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    location_precision: LocationPrecision = LocationPrecision.STATE
    verification_status: VerificationStatus = VerificationStatus.UNCONFIRMED
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    corroboration_count: int = Field(default=0, ge=0)
    current_status: IncidentStatus = IncidentStatus.ONGOING
    headline: Optional[str] = None
    fields: list[CitedField] = Field(default_factory=list)
    source_ids: list[UUID] = Field(default_factory=list)


class IncidentSummary(BaseModel):
    incident_id: UUID
    event_type: EventType
    date_occurred: Optional[date] = None
    date_reported: date
    state: str
    lga: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    verification_status: VerificationStatus
    confidence_score: float
    corroboration_count: int
    current_status: IncidentStatus
    headline: Optional[str] = None


class LinkedSource(BaseModel):
    source: SourceRecord
    role: SourceRole


class IncidentDetail(IncidentSummary):
    location_precision: LocationPrecision
    published_at: Optional[datetime] = None
    fields: list[CitedField] = Field(default_factory=list)
    status_history: list[StatusHistoryEntry] = Field(default_factory=list)
    sources: list[LinkedSource] = Field(default_factory=list)


class GeoBubble(BaseModel):
    geo_id: str
    name: str
    level: str  # state | lga
    state: str
    lga: Optional[str] = None
    lat: float
    lng: float
    count: int
    intensity: float
    by_type: dict[str, int] = Field(default_factory=dict)
    dominant_verification: Optional[VerificationStatus] = None
    dominant_outcome: Optional[str] = None  # captive | resolved
