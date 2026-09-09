export type VerificationStatus =
  | "unconfirmed"
  | "reported"
  | "verified"
  | "official_confirmation";

export type GeoBubble = {
  geo_id: string;
  name: string;
  level: string;
  state: string;
  lga?: string | null;
  lat: number;
  lng: number;
  count: number;
  intensity: number;
  by_type: Record<string, number>;
  dominant_verification?: VerificationStatus | null;
};

export type IncidentSummary = {
  incident_id: string;
  event_type: string;
  date_occurred?: string | null;
  date_reported: string;
  state: string;
  lga?: string | null;
  lat?: number | null;
  lng?: number | null;
  verification_status: VerificationStatus;
  confidence_score: number;
  corroboration_count: number;
  current_status: string;
  headline?: string | null;
};

export type SourceRecord = {
  source_id: string;
  url: string;
  outlet: string;
  source_type: string;
  fetched_at: string;
  reliability_tier: number;
  excerpt?: string | null;
};

export type IncidentDetail = IncidentSummary & {
  location_precision?: string;
  published_at?: string | null;
  fields: Array<{
    field_name: string;
    value: unknown;
    source_id: string;
    source_span: string;
    confidence: number;
  }>;
  status_history: Array<{
    from_status?: string | null;
    to_status: string;
    changed_at: string;
    source_id: string;
    note?: string | null;
  }>;
  sources: Array<{ role: string; source: SourceRecord }>;
};

export type ReviewItem = {
  queue_id: string;
  incident_id?: string | null;
  status: string;
  priority: number;
  reason?: string | null;
  created_at: string;
  candidate_json: {
    publish_preview?: {
      event_type?: string;
      state?: string;
      lga?: string;
      headline?: string;
      corroboration_count?: number;
      verification_status?: string;
    };
    reason?: string;
  };
};
