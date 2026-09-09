import type { GeoBubble, IncidentDetail, IncidentSummary, ReviewItem } from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

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

export function fetchBubbles(level: "lga" | "state" = "lga"): Promise<GeoBubble[]> {
  return getJson(`/api/map/bubbles?level=${level}&min_status=reported`);
}

export function fetchBubbleIncidents(geoId: string): Promise<IncidentSummary[]> {
  return getJson(`/api/map/bubbles/${encodeURIComponent(geoId)}/incidents`);
}

export function fetchIncident(id: string): Promise<IncidentDetail> {
  return getJson(`/api/incidents/${id}`);
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
      else if (Array.isArray(body?.detail)) detail = body.detail.map((d: { msg?: string }) => d.msg).join("; ");
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  return res.json();
}

export { API_BASE };
