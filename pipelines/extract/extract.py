"""Constrained extraction: rule-based MVP + optional LLM hook.

The LLM path must only fill ExtractionResult fields with source_span citations.
Invented coordinates/counts are rejected.
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional

from hummingbird_schemas import (
    BronzePayload,
    EventType,
    ExtractedField,
    ExtractionResult,
    IncidentStatus,
    LocationPrecision,
)
from hummingbird_schemas.geo import normalize_state

ROOT = Path(__file__).resolve().parents[2]
SILVER_DIR = ROOT / "data" / "silver"

NIGERIA_STATES = [
    "Abia", "Adamawa", "Akwa Ibom", "Anambra", "Bauchi", "Bayelsa", "Benue",
    "Borno", "Cross River", "Delta", "Ebonyi", "Edo", "Ekiti", "Enugu", "FCT",
    "Gombe", "Imo", "Jigawa", "Kaduna", "Kano", "Katsina", "Kebbi", "Kogi",
    "Kwara", "Lagos", "Nasarawa", "Niger", "Ogun", "Ondo", "Osun", "Oyo",
    "Plateau", "Rivers", "Sokoto", "Taraba", "Yobe", "Zamfara",
]

EVENT_PATTERNS: list[tuple[EventType, re.Pattern[str]]] = [
    (EventType.KIDNAP, re.compile(r"\b(kidnap|abduct|abduction|ransom)\b", re.I)),
    (EventType.SCAM, re.compile(r"\b(scam|defraud|fraud syndicate|crypto returns)\b", re.I)),
    (EventType.ROBBERY, re.compile(r"\b(robbery|armed robbers?)\b", re.I)),
    (EventType.TERRORISM, re.compile(r"\b(insurgent|terror|boko haram|iswap)\b", re.I)),
    (EventType.PROTEST, re.compile(r"\b(protest|demonstration)\b", re.I)),
    (EventType.EXPLOSION, re.compile(r"\b(explosion|ied|bomb)\b", re.I)),
    (EventType.BATTLE, re.compile(r"\b(clash|gunbattle|armed clash)\b", re.I)),
]

COUNT_RE = re.compile(
    r"\b(?:abducted|kidnapped|killed|defrauded)?\s*(?:at least\s*)?(\d{1,3})\s+"
    r"(?:travelers|passengers|villagers|residents|people|victims|students)\b",
    re.I,
)

STATUS_PATTERNS: list[tuple[IncidentStatus, re.Pattern[str]]] = [
    (IncidentStatus.RELEASED, re.compile(r"\b(released|freed)\b", re.I)),
    (IncidentStatus.RESCUED, re.compile(r"\b(rescued)\b", re.I)),
    (IncidentStatus.IN_NEGOTIATION, re.compile(r"\b(negotiat)\b", re.I)),
    (IncidentStatus.CASUALTY_CONFIRMED, re.compile(r"\b(killed|fatalit|dead)\b", re.I)),
]


def _find_span(text: str, pattern: re.Pattern[str]) -> Optional[str]:
    m = pattern.search(text)
    if not m:
        return None
    start = max(0, m.start() - 40)
    end = min(len(text), m.end() + 40)
    return text[start:end].strip()


def detect_event_type(text: str) -> tuple[EventType, Optional[str]]:
    for et, pat in EVENT_PATTERNS:
        span = _find_span(text, pat)
        if span:
            return et, span
    return EventType.OTHER, None


def detect_state(text: str) -> tuple[Optional[str], Optional[str]]:
    for state in sorted(NIGERIA_STATES, key=len, reverse=True):
        pat = re.compile(rf"\b{re.escape(state)}\b", re.I)
        span = _find_span(text, pat)
        if span:
            return normalize_state(state), span
    # Nationwide aggregate / unspecified location within Nigeria
    m = re.search(
        r"\b(?:across|throughout|in)\s+Nigeria\b|\bNigeria\b|\bNigerian\b",
        text,
        re.I,
    )
    if m:
        span = text[max(0, m.start() - 20) : min(len(text), m.end() + 20)].strip()
        return "Nigeria", span
    return None, None


def detect_lga(text: str, state_span: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    # Lightweight LGA cue: "<Name> Local Government" or "in <Name> LGA"
    m = re.search(r"\bin\s+([A-Z][a-zA-Z\- ]+?)\s+(?:Local Government|LGA)\b", text)
    if not m:
        m = re.search(r"\b([A-Z][a-zA-Z\- ]+?)\s+Local Government Area\b", text)
    if not m:
        return None, None
    name = m.group(1).strip()
    span = text[max(0, m.start() - 20) : min(len(text), m.end() + 20)].strip()
    return name, span


def detect_status(text: str) -> tuple[IncidentStatus, Optional[str]]:
    for status, pat in STATUS_PATTERNS:
        span = _find_span(text, pat)
        if span:
            return status, span
    return IncidentStatus.ONGOING, None


def extract_from_bronze(payload: BronzePayload) -> ExtractionResult:
    text = f"{payload.title or ''}\n{payload.body or ''}".strip()
    if len(text) < 40:
        return ExtractionResult(
            event_type=EventType.OTHER,
            source_text_hash=payload.content_hash,
            rejected=True,
            reject_reason="body too short",
        )

    event_type, event_span = detect_event_type(text)
    state, state_span = detect_state(text)
    lga, lga_span = detect_lga(text, state_span)
    status, status_span = detect_status(text)

    # National aggregates must not invent LGA pins
    if state == "Nigeria":
        lga, lga_span = None, None

    fields: list[ExtractedField] = []
    if event_span:
        fields.append(
            ExtractedField(
                field_name="event_type",
                value=event_type.value,
                source_span=event_span,
                confidence=0.8,
            )
        )
    if state and state_span:
        fields.append(
            ExtractedField(
                field_name="state",
                value=state,
                source_span=state_span,
                confidence=0.85,
            )
        )
    if lga and lga_span:
        fields.append(
            ExtractedField(
                field_name="lga",
                value=lga,
                source_span=lga_span,
                confidence=0.7,
            )
        )

    count_m = COUNT_RE.search(text)
    if count_m:
        span = text[max(0, count_m.start() - 20) : min(len(text), count_m.end() + 20)].strip()
        fields.append(
            ExtractedField(
                field_name="victim_count",
                value=int(count_m.group(1)),
                source_span=span,
                confidence=0.75,
            )
        )

    if status_span:
        fields.append(
            ExtractedField(
                field_name="current_status",
                value=status.value,
                source_span=status_span,
                confidence=0.7,
            )
        )

    rejected = state is None
    return ExtractionResult(
        event_type=event_type,
        date_occurred=None,
        date_reported=date.today(),
        state=state,
        lga=lga,
        location_precision=LocationPrecision.LGA if lga else LocationPrecision.STATE,
        current_status=status,
        headline=(payload.title or text[:120]).strip(),
        fields=fields,
        source_text_hash=payload.content_hash,
        rejected=rejected,
        reject_reason="missing state" if rejected else None,
    )


LLM_SYSTEM_PROMPT = """You are an extraction engine for Nigerian security reports.
Extract ONLY facts explicitly present in the source text.
Every field MUST include a source_span that is a verbatim substring of the source.
Never invent coordinates, counts, names, or dates that are not in the text.
If a fact is missing, omit the field. Return JSON matching ExtractionResult."""


def extract_with_llm_stub(payload: BronzePayload) -> ExtractionResult:
    """Placeholder for Databricks/LLM structured output jobs.

    Production should call an LLM with JSON schema + span validation that
    asserts each source_span is a substring of the bronze body.
    """
    result = extract_from_bronze(payload)
    # Span validation gate (same gate LLM outputs must pass)
    body = f"{payload.title or ''}\n{payload.body or ''}"
    for field in result.fields:
        if field.source_span not in body and field.source_span.lower() not in body.lower():
            result.rejected = True
            result.reject_reason = f"span not grounded: {field.field_name}"
            break
    return result


def run_extract(bronze_path: Path) -> Path:
    SILVER_DIR.mkdir(parents=True, exist_ok=True)
    out = SILVER_DIR / f"extracted_{bronze_path.stem}.jsonl"
    count = 0
    with bronze_path.open(encoding="utf-8") as src, out.open("w", encoding="utf-8") as dst:
        for line in src:
            if not line.strip():
                continue
            payload = BronzePayload.model_validate_json(line)
            result = extract_with_llm_stub(payload)
            row = {
                "bronze": payload.model_dump(mode="json"),
                "extraction": result.model_dump(mode="json"),
                "extracted_at": datetime.now(timezone.utc).isoformat(),
            }
            dst.write(json.dumps(row) + "\n")
            count += 1
    print(f"[extract] {count} rows → {out}")
    return out


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("bronze_path", type=Path)
    args = parser.parse_args()
    run_extract(args.bronze_path)
