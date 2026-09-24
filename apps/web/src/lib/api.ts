import type { GeoBubble, IncidentDetail, IncidentSummary, ReviewItem } from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const DETAIL_TTL_MS = 60_000;

type DetailCacheEntry = {
  detail: IncidentDetail;
  fetchedAt: number;
};

const detailCache = new Map<string, DetailCacheEntry>();

export type DateRangeFilter = {
  dateFrom?: string | null;
  dateTo?: string | null;
};

export function invalidateIncidentCache(): void {
  detailCache.clear();
}

export function getCachedIncident(
  id: string,
): { detail: IncidentDetail; fresh: boolean } | null {
  const entry = detailCache.get(id);
  if (!entry) return null;
  return {
    detail: entry.detail,
    fresh: Date.now() - entry.fetchedAt < DETAIL_TTL_MS,
  };
}

function setCachedIncident(id: string, detail: IncidentDetail): void {
  detailCache.set(id, { detail, fetchedAt: Date.now() });
}

/** Build a header-ready partial detail from list/search summary (body empty until fetch). */
export function summaryToPartialDetail(summary: IncidentSummary): IncidentDetail {
  return {
    ...summary,
    fields: [],
    status_history: [],
    sources: [],
  };
}

async function getJson<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`API ${res.status}: ${path}`);
  }
  return res.json() as Promise<T>;
}

function withDateParams(params: URLSearchParams, range?: DateRangeFilter) {
  if (range?.dateFrom) params.set("date_from", range.dateFrom);
  if (range?.dateTo) params.set("date_to", range.dateTo);
}

export function fetchBubbles(
  level: "lga" | "state" = "lga",
  range?: DateRangeFilter,
): Promise<GeoBubble[]> {
  const params = new URLSearchParams({
    level,
    min_status: "reported",
  });
  withDateParams(params, range);
  return getJson(`/api/map/bubbles?${params.toString()}`);
}

export function fetchBubbleIncidents(
  geoId: string,
  range?: DateRangeFilter,
): Promise<IncidentSummary[]> {
  const params = new URLSearchParams();
  withDateParams(params, range);
  const qs = params.toString();
  return getJson(
    `/api/map/bubbles/${encodeURIComponent(geoId)}/incidents${qs ? `?${qs}` : ""}`,
  );
}

export async function fetchIncident(id: string): Promise<IncidentDetail> {
  const detail = await getJson<IncidentDetail>(`/api/incidents/${id}`);
  setCachedIncident(id, detail);
  return detail;
}

export function searchIncidents(
  q: string,
  limit = 20,
  range?: DateRangeFilter,
): Promise<IncidentSummary[]> {
  const params = new URLSearchParams({
    q,
    limit: String(limit),
    min_status: "reported",
  });
  withDateParams(params, range);
  return getJson(`/api/incidents/search?${params.toString()}`);
}

export function fetchReviewQueue(): Promise<ReviewItem[]> {
  const token = process.env.NEXT_PUBLIC_MODERATOR_TOKEN || "dev-moderator-token";
  return getJson(`/api/review?status=pending`, {
    headers: { Authorization: `Bearer ${token}` },
  });
}

export async function approveReview(queueId: string): Promise<{ incident_id: string }> {
  const token = process.env.NEXT_PUBLIC_MODERATOR_TOKEN || "dev-moderator-token";
  return getJson(`/api/review/${queueId}/approve`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
  });
}

export async function rejectReview(queueId: string, notes?: string): Promise<void> {
  const token = process.env.NEXT_PUBLIC_MODERATOR_TOKEN || "dev-moderator-token";
  await getJson(`/api/review/${queueId}/reject`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: JSON.stringify({ notes: notes || "" }),
  });
}

export async function submitIncidentReport(
  formData: FormData,
): Promise<{ queue_id: string; notified: boolean }> {
  const res = await fetch(`${API_BASE}/api/reports`, {
    method: "POST",
    body: formData,
    cache: "no-store",
  });
  if (!res.ok) {
    let detail = `API ${res.status}`;
    try {
      const body = await res.json();
      if (typeof body?.detail === "string") detail = body.detail;
      else if (Array.isArray(body?.detail))
        detail = body.detail.map((d: { msg?: string }) => d.msg).join("; ");
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  return res.json();
}

export { API_BASE };
