"""Demo in-memory store so the map works without Postgres during local UI work."""

from __future__ import annotations

import math
from copy import deepcopy
from datetime import date, datetime, timezone
from typing import Any
from uuid import UUID

DEMO_SOURCES: dict[str, dict[str, Any]] = {
    "11111111-1111-1111-1111-111111111101": {
        "source_id": "11111111-1111-1111-1111-111111111101",
        "url": "https://example.com/punch/kaduna-kidnap",
        "outlet": "Punch",
        "source_type": "news",
        "fetched_at": "2026-09-06T10:00:00Z",
        "reliability_tier": 2,
        "excerpt": "Gunmen abducted 12 travelers along the Kaduna-Abuja highway.",
    },
    "11111111-1111-1111-1111-111111111102": {
        "source_id": "11111111-1111-1111-1111-111111111102",
        "url": "https://example.com/dailytrust/kaduna-kidnap",
        "outlet": "Daily Trust",
        "source_type": "news",
        "fetched_at": "2026-09-06T11:00:00Z",
        "reliability_tier": 2,
        "excerpt": "At least 12 passengers were kidnapped on the Kaduna-Abuja road.",
    },
    "11111111-1111-1111-1111-111111111103": {
        "source_id": "11111111-1111-1111-1111-111111111103",
        "url": "https://example.com/premiumtimes/borno-attack",
        "outlet": "Premium Times",
        "source_type": "news",
        "fetched_at": "2026-09-03T09:00:00Z",
        "reliability_tier": 2,
        "excerpt": "Residents reported an attack on a community in Borno State.",
    },
    "11111111-1111-1111-1111-111111111104": {
        "source_id": "11111111-1111-1111-1111-111111111104",
        "url": "https://example.com/police/borno-statement",
        "outlet": "Police PRO Borno",
        "source_type": "official",
        "fetched_at": "2026-09-04T08:00:00Z",
        "reliability_tier": 1,
        "excerpt": "Police confirm armed assault in southern Borno; investigation ongoing.",
    },
    "11111111-1111-1111-1111-111111111105": {
        "source_id": "11111111-1111-1111-1111-111111111105",
        "url": "https://example.com/vanguard/lagos-scam",
        "outlet": "Vanguard",
        "source_type": "news",
        "fetched_at": "2026-09-07T14:00:00Z",
        "reliability_tier": 2,
        "excerpt": "Investment scam syndicate defrauded residents in Lagos Island.",
    },
    "11111111-1111-1111-1111-111111111106": {
        "source_id": "11111111-1111-1111-1111-111111111106",
        "url": "https://example.com/premiumtimes/lagos-scam",
        "outlet": "Premium Times",
        "source_type": "news",
        "fetched_at": "2026-09-07T15:00:00Z",
        "reliability_tier": 2,
        "excerpt": "Two outlets report a coordinated crypto investment scam in Lagos.",
    },
}

DEMO_INCIDENTS: list[dict[str, Any]] = [
    {
        "incident_id": "22222222-2222-2222-2222-222222222201",
        "event_type": "kidnap",
        "date_occurred": "2026-09-05",
        "date_reported": "2026-09-06",
        "state": "Kaduna",
        "lga": "Chikun",
        "lat": 10.45,
        "lng": 7.4165,
        "location_precision": "lga",
        "verification_status": "verified",
        "confidence_score": 0.85,
        "corroboration_count": 2,
        "current_status": "ongoing",
        "headline": "Travelers abducted on Kaduna-Abuja highway",
        "published_at": "2026-09-07T10:00:00Z",
        "source_ids": [
            "11111111-1111-1111-1111-111111111101",
            "11111111-1111-1111-1111-111111111102",
        ],
        "fields": [
            {
                "field_name": "victim_count",
                "value": 12,
                "source_id": "11111111-1111-1111-1111-111111111101",
                "source_span": "Gunmen abducted 12 travelers along the Kaduna-Abuja highway.",
                "confidence": 0.9,
            },
            {
                "field_name": "victim_type",
                "value": "travelers",
                "source_id": "11111111-1111-1111-1111-111111111101",
                "source_span": "Gunmen abducted 12 travelers along the Kaduna-Abuja highway.",
                "confidence": 0.85,
            },
        ],
        "status_history": [
            {
                "from_status": None,
                "to_status": "ongoing",
                "changed_at": "2026-09-06T10:00:00Z",
                "source_id": "11111111-1111-1111-1111-111111111101",
                "note": "Initial report",
            }
        ],
    },
    {
        "incident_id": "22222222-2222-2222-2222-222222222202",
        "event_type": "terrorism",
        "date_occurred": "2026-09-02",
        "date_reported": "2026-09-03",
        "state": "Borno",
        "lga": "Chibok",
        "lat": 10.869,
        "lng": 12.847,
        "location_precision": "lga",
        "verification_status": "official_confirmation",
        "confidence_score": 0.95,
        "corroboration_count": 2,
        "current_status": "unresolved",
        "headline": "Armed assault reported in southern Borno",
        "published_at": "2026-09-05T10:00:00Z",
        "source_ids": [
            "11111111-1111-1111-1111-111111111103",
            "11111111-1111-1111-1111-111111111104",
        ],
        "fields": [],
        "status_history": [
            {
                "from_status": None,
                "to_status": "unresolved",
                "changed_at": "2026-09-03T09:00:00Z",
                "source_id": "11111111-1111-1111-1111-111111111104",
                "note": "Official confirmation",
            }
        ],
    },
    {
        "incident_id": "22222222-2222-2222-2222-222222222203",
        "event_type": "scam",
        "date_occurred": "2026-09-06",
        "date_reported": "2026-09-07",
        "state": "Lagos",
        "lga": "Lagos Island",
        "lat": 6.455,
        "lng": 3.401,
        "location_precision": "lga",
        "verification_status": "reported",
        "confidence_score": 0.7,
        "corroboration_count": 2,
        "current_status": "ongoing",
        "headline": "Investment scam syndicate active in Lagos Island",
        "published_at": "2026-09-07T18:00:00Z",
        "source_ids": [
            "11111111-1111-1111-1111-111111111105",
            "11111111-1111-1111-1111-111111111106",
        ],
        "fields": [
            {
                "field_name": "victim_type",
                "value": "residents",
                "source_id": "11111111-1111-1111-1111-111111111105",
                "source_span": "Investment scam syndicate defrauded residents in Lagos Island.",
                "confidence": 0.8,
            }
        ],
        "status_history": [],
    },
    {
        "incident_id": "22222222-2222-2222-2222-222222222204",
        "event_type": "robbery",
        "date_occurred": "2026-09-04",
        "date_reported": "2026-09-04",
        "state": "Rivers",
        "lga": "Port Harcourt",
        "lat": 4.8156,
        "lng": 7.013,
        "location_precision": "lga",
        "verification_status": "reported",
        "confidence_score": 0.65,
        "corroboration_count": 2,
        "current_status": "unresolved",
        "headline": "Armed robbery along Port Harcourt arterial road",
        "published_at": "2026-09-06T10:00:00Z",
        "source_ids": [
            "11111111-1111-1111-1111-111111111101",
            "11111111-1111-1111-1111-111111111102",
        ],
        "fields": [],
        "status_history": [],
    },
    {
        "incident_id": "22222222-2222-2222-2222-222222222205",
        "event_type": "kidnap",
        "date_occurred": "2026-08-29",
        "date_reported": "2026-08-30",
        "state": "Zamfara",
        "lga": "Anka",
        "lat": 12.11,
        "lng": 5.95,
        "location_precision": "lga",
        "verification_status": "verified",
        "confidence_score": 0.8,
        "corroboration_count": 3,
        "current_status": "released",
        "headline": "Villagers kidnapped in Anka LGA later released",
        "published_at": "2026-09-04T10:00:00Z",
        "source_ids": [
            "11111111-1111-1111-1111-111111111102",
            "11111111-1111-1111-1111-111111111103",
        ],
        "fields": [
            {
                "field_name": "victim_count",
                "value": 8,
                "source_id": "11111111-1111-1111-1111-111111111102",
                "source_span": "Eight villagers were kidnapped in Anka and later released.",
                "confidence": 0.75,
            }
        ],
        "status_history": [
            {
                "from_status": None,
                "to_status": "ongoing",
                "changed_at": "2026-08-30T10:00:00Z",
                "source_id": "11111111-1111-1111-1111-111111111102",
                "note": "Initial abduction report",
            },
            {
                "from_status": "ongoing",
                "to_status": "released",
                "changed_at": "2026-09-04T10:00:00Z",
                "source_id": "11111111-1111-1111-1111-111111111103",
                "note": "Victims reported released",
            },
        ],
    },
]

DEMO_REVIEW: list[dict[str, Any]] = [
    {
        "queue_id": "33333333-3333-3333-3333-333333333301",
        "incident_id": None,
        "status": "pending",
        "priority": 50,
        "reason": "Single source — needs corroboration or moderator decision",
        "created_at": "2026-09-08T08:00:00Z",
        "candidate_json": {
            "verification_status": "unconfirmed",
            "publish_preview": {
                "event_type": "protest",
                "state": "Oyo",
                "lga": "Ibadan North",
                "headline": "Protest over insecurity in Ibadan",
                "corroboration_count": 1,
                "verification_status": "unconfirmed",
            },
            "candidate": {
                "corroboration_count": 1,
                "independent_outlets": ["Punch"],
                "primary": {
                    "bronze": {
                        "url": "https://example.com/punch/ibadan-protest",
                        "outlet": "Punch",
                        "source_type": "news",
                        "fetched_at": "2026-09-08T07:00:00Z",
                        "content_hash": "demo-protest",
                        "title": "Protest over insecurity in Ibadan",
                        "body": "Residents protested insecurity in Ibadan North, Oyo State.",
                    },
                    "extraction": {
                        "event_type": "protest",
                        "state": "Oyo",
                        "lga": "Ibadan North",
                        "headline": "Protest over insecurity in Ibadan",
                        "current_status": "ongoing",
                        "location_precision": "lga",
                        "date_reported": str(date.today()),
                        "fields": [
                            {
                                "field_name": "state",
                                "value": "Oyo",
                                "source_span": "Ibadan North, Oyo State",
                                "confidence": 0.8,
                            }
                        ],
                    },
                },
                "members": [],
            },
        },
    }
]

PUBLIC_STATUSES = {"reported", "verified", "official_confirmation"}


class DemoStore:
    def __init__(self) -> None:
        self.incidents = deepcopy(DEMO_INCIDENTS)
        self.sources = deepcopy(DEMO_SOURCES)
        self.review = deepcopy(DEMO_REVIEW)

    def list_public_incidents(
        self,
        min_status: str = "reported",
        types: list[str] | None = None,
        include_unconfirmed: bool = False,
    ) -> list[dict[str, Any]]:
        allowed = set(PUBLIC_STATUSES)
        if include_unconfirmed or min_status == "unconfirmed":
            allowed.add("unconfirmed")
        order = ["unconfirmed", "reported", "verified", "official_confirmation"]
        min_idx = order.index(min_status) if min_status in order else 1
        allowed = {s for s in allowed if order.index(s) >= min_idx or s in allowed}
        # simpler: default reported+
        if not include_unconfirmed and min_status == "reported":
            allowed = set(PUBLIC_STATUSES)
        rows = [i for i in self.incidents if i["verification_status"] in allowed and i.get("published_at")]
        if types:
            rows = [i for i in rows if i["event_type"] in types]
        return rows

    def bubbles(self, level: str = "lga", **kwargs: Any) -> list[dict[str, Any]]:
        rows = self.list_public_incidents(**kwargs)
        buckets: dict[str, list[dict[str, Any]]] = {}
        for i in rows:
            if level == "state":
                geo_id = f"state:{i['state'].lower()}"
                name = i["state"]
                lga = None
            else:
                if i.get("lga"):
                    geo_id = f"{i['state'].lower()}:{i['lga'].lower()}"
                    name = i["lga"]
                    lga = i["lga"]
                else:
                    geo_id = f"state:{i['state'].lower()}"
                    name = i["state"]
                    lga = None
            buckets.setdefault(geo_id, []).append({**i, "_name": name, "_lga": lga})

        out: list[dict[str, Any]] = []
        for geo_id, items in buckets.items():
            by_type: dict[str, int] = {}
            for it in items:
                by_type[it["event_type"]] = by_type.get(it["event_type"], 0) + 1
            # dominant verification
            counts: dict[str, int] = {}
            for it in items:
                counts[it["verification_status"]] = counts.get(it["verification_status"], 0) + 1
            dominant = max(counts, key=counts.get) if counts else None
            out.append(
                {
                    "geo_id": geo_id,
                    "name": items[0]["_name"],
                    "level": "lga" if items[0].get("_lga") else "state",
                    "state": items[0]["state"],
                    "lga": items[0].get("_lga"),
                    "lat": sum(i["lat"] for i in items) / len(items),
                    "lng": sum(i["lng"] for i in items) / len(items),
                    "count": len(items),
                    "intensity": math.log(len(items) + 1),
                    "by_type": by_type,
                    "dominant_verification": dominant,
                }
            )
        return out

    def incidents_for_geo(self, geo_id: str, **kwargs: Any) -> list[dict[str, Any]]:
        bubbles = {b["geo_id"]: b for b in self.bubbles(**kwargs)}
        if geo_id not in bubbles:
            return []
        b = bubbles[geo_id]
        rows = self.list_public_incidents(**kwargs)
        result = []
        for i in rows:
            if b["level"] == "state":
                if i["state"].lower() == b["state"].lower():
                    result.append(i)
            else:
                if (
                    i["state"].lower() == b["state"].lower()
                    and (i.get("lga") or "").lower() == (b.get("lga") or "").lower()
                ):
                    result.append(i)
        return result

    def get_incident(self, incident_id: str) -> dict[str, Any] | None:
        for i in self.incidents:
            if i["incident_id"] == incident_id:
                detail = deepcopy(i)
                sources = []
                for idx, sid in enumerate(detail.get("source_ids") or []):
                    src = self.sources.get(sid)
                    if src:
                        sources.append(
                            {
                                "role": "primary" if idx == 0 else "corroborating",
                                "source": src,
                            }
                        )
                detail["sources"] = sources
                return detail
        return None

    def list_review(self, status: str = "pending") -> list[dict[str, Any]]:
        return [r for r in self.review if r["status"] == status]

    def enqueue_tip(self, candidate: dict[str, Any]) -> str:
        queue_id = candidate["queue_id"]
        self.review.append(
            {
                "queue_id": queue_id,
                "incident_id": None,
                "candidate_json": deepcopy(candidate),
                "status": "pending",
                "priority": candidate.get("priority", 40),
                "reason": candidate.get("reason"),
                "reviewer_notes": None,
                "created_at": candidate.get("created_at")
                or datetime.now(timezone.utc).isoformat(),
                "reviewed_at": None,
                "reviewed_by": None,
            }
        )
        return queue_id

    def approve(self, queue_id: str, reviewer: str) -> str | None:
        for r in self.review:
            if r["queue_id"] == queue_id and r["status"] == "pending":
                preview = (r["candidate_json"].get("publish_preview") or {})
                new_id = str(UUID(int=0x44444444444444444444444444444441))
                # use random-ish unique
                from uuid import uuid4

                new_id = str(uuid4())
                incident = {
                    "incident_id": new_id,
                    "event_type": preview.get("event_type") or "other",
                    "date_occurred": None,
                    "date_reported": date.today().isoformat(),
                    "state": preview.get("state") or "Unknown",
                    "lga": preview.get("lga"),
                    "lat": 7.4,
                    "lng": 3.9,
                    "location_precision": "lga",
                    "verification_status": "verified",
                    "confidence_score": 0.6,
                    "corroboration_count": preview.get("corroboration_count") or 1,
                    "current_status": "ongoing",
                    "headline": preview.get("headline"),
                    "published_at": datetime.now(timezone.utc).isoformat(),
                    "source_ids": [],
                    "fields": [],
                    "status_history": [],
                }
                # rough centroid for Oyo
                if incident["state"] == "Oyo":
                    incident["lat"], incident["lng"] = 8.1574, 3.6147
                self.incidents.append(incident)
                r["status"] = "approved"
                r["incident_id"] = new_id
                r["reviewed_by"] = reviewer
                return new_id
        return None

    def reject(self, queue_id: str, reviewer: str, notes: str = "") -> bool:
        for r in self.review:
            if r["queue_id"] == queue_id and r["status"] == "pending":
                r["status"] = "rejected"
                r["reviewed_by"] = reviewer
                r["reviewer_notes"] = notes
                return True
        return False


demo_store = DemoStore()
