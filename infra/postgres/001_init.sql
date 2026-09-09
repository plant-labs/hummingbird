-- Hummingbird serving schema (Postgres + PostGIS)
-- Product source of truth for map, moderation, and SSE.

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TYPE event_type AS ENUM (
  'kidnap', 'robbery', 'terrorism', 'protest', 'scam',
  'battle', 'explosion', 'other'
);

CREATE TYPE verification_status AS ENUM (
  'unconfirmed', 'reported', 'verified', 'official_confirmation'
);

CREATE TYPE incident_status AS ENUM (
  'ongoing', 'in_negotiation', 'released', 'rescued',
  'casualty_confirmed', 'unresolved'
);

CREATE TYPE location_precision AS ENUM ('exact', 'lga', 'state');

CREATE TYPE source_type AS ENUM ('news', 'social', 'official', 'crowd');

CREATE TYPE source_role AS ENUM ('primary', 'corroborating');

CREATE TYPE review_queue_status AS ENUM (
  'pending', 'approved', 'rejected', 'needs_sources'
);

-- ---------------------------------------------------------------------------
-- sources
-- ---------------------------------------------------------------------------
CREATE TABLE sources (
  source_id       UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  url             TEXT NOT NULL,
  outlet          TEXT NOT NULL,
  source_type     source_type NOT NULL,
  fetched_at      TIMESTAMPTZ NOT NULL,
  published_at    TIMESTAMPTZ,
  raw_ref         TEXT,
  reliability_tier SMALLINT NOT NULL DEFAULT 3 CHECK (reliability_tier BETWEEN 1 AND 5),
  excerpt         TEXT,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (url)
);

CREATE INDEX sources_outlet_idx ON sources (outlet);
CREATE INDEX sources_type_idx ON sources (source_type);

-- ---------------------------------------------------------------------------
-- incidents
-- ---------------------------------------------------------------------------
CREATE TABLE incidents (
  incident_id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  event_type           event_type NOT NULL,
  date_occurred        DATE,
  date_reported        DATE NOT NULL,
  state                TEXT NOT NULL,
  lga                  TEXT,
  geom                 geography(Point, 4326),
  location_precision   location_precision NOT NULL DEFAULT 'state',
  verification_status  verification_status NOT NULL DEFAULT 'unconfirmed',
  confidence_score     REAL NOT NULL DEFAULT 0 CHECK (confidence_score BETWEEN 0 AND 1),
  corroboration_count  INT NOT NULL DEFAULT 0 CHECK (corroboration_count >= 0),
  current_status       incident_status NOT NULL DEFAULT 'ongoing',
  headline             TEXT,
  published_at         TIMESTAMPTZ,
  created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX incidents_state_lga_idx ON incidents (state, lga);
CREATE INDEX incidents_verification_idx ON incidents (verification_status);
CREATE INDEX incidents_event_type_idx ON incidents (event_type);
CREATE INDEX incidents_date_reported_idx ON incidents (date_reported);
CREATE INDEX incidents_geom_idx ON incidents USING GIST (geom);
CREATE INDEX incidents_published_idx ON incidents (published_at)
  WHERE published_at IS NOT NULL;

-- ---------------------------------------------------------------------------
-- incident_fields (per-field citations)
-- ---------------------------------------------------------------------------
CREATE TABLE incident_fields (
  id            BIGSERIAL PRIMARY KEY,
  incident_id   UUID NOT NULL REFERENCES incidents(incident_id) ON DELETE CASCADE,
  field_name    TEXT NOT NULL,
  value_json    JSONB NOT NULL,
  source_id     UUID NOT NULL REFERENCES sources(source_id),
  source_span   TEXT NOT NULL CHECK (length(trim(source_span)) > 0),
  confidence    REAL NOT NULL DEFAULT 0.5 CHECK (confidence BETWEEN 0 AND 1),
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (incident_id, field_name, source_id)
);

CREATE INDEX incident_fields_incident_idx ON incident_fields (incident_id);

-- ---------------------------------------------------------------------------
-- status_history
-- ---------------------------------------------------------------------------
CREATE TABLE status_history (
  id            BIGSERIAL PRIMARY KEY,
  incident_id   UUID NOT NULL REFERENCES incidents(incident_id) ON DELETE CASCADE,
  from_status   incident_status,
  to_status     incident_status NOT NULL,
  changed_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  source_id     UUID NOT NULL REFERENCES sources(source_id),
  note          TEXT
);

CREATE INDEX status_history_incident_idx ON status_history (incident_id, changed_at);

-- ---------------------------------------------------------------------------
-- incident_sources
-- ---------------------------------------------------------------------------
CREATE TABLE incident_sources (
  incident_id   UUID NOT NULL REFERENCES incidents(incident_id) ON DELETE CASCADE,
  source_id     UUID NOT NULL REFERENCES sources(source_id),
  role          source_role NOT NULL DEFAULT 'corroborating',
  linked_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (incident_id, source_id)
);

-- ---------------------------------------------------------------------------
-- review_queue
-- ---------------------------------------------------------------------------
CREATE TABLE review_queue (
  queue_id        UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  incident_id     UUID REFERENCES incidents(incident_id) ON DELETE SET NULL,
  candidate_json  JSONB NOT NULL,
  status          review_queue_status NOT NULL DEFAULT 'pending',
  priority        INT NOT NULL DEFAULT 100,
  reason          TEXT,
  reviewer_notes  TEXT,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  reviewed_at     TIMESTAMPTZ,
  reviewed_by     TEXT
);

CREATE INDEX review_queue_status_idx ON review_queue (status, priority, created_at);

-- ---------------------------------------------------------------------------
-- geo_agg_cache (heat bubbles)
-- ---------------------------------------------------------------------------
CREATE TABLE geo_agg_cache (
  geo_id                 TEXT PRIMARY KEY,
  level                  TEXT NOT NULL CHECK (level IN ('state', 'lga')),
  name                   TEXT NOT NULL,
  state                  TEXT NOT NULL,
  lga                    TEXT,
  lat                    DOUBLE PRECISION NOT NULL,
  lng                    DOUBLE PRECISION NOT NULL,
  count                  INT NOT NULL DEFAULT 0,
  intensity              REAL NOT NULL DEFAULT 0,
  by_type                JSONB NOT NULL DEFAULT '{}'::jsonb,
  dominant_verification  verification_status,
  updated_at             TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX geo_agg_cache_level_idx ON geo_agg_cache (level);
CREATE INDEX geo_agg_cache_state_idx ON geo_agg_cache (state);

-- ---------------------------------------------------------------------------
-- updated_at trigger
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER incidents_set_updated_at
  BEFORE UPDATE ON incidents
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ---------------------------------------------------------------------------
-- LISTEN/NOTIFY for live map / SSE
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION notify_incident_change()
RETURNS TRIGGER AS $$
DECLARE
  payload JSON;
BEGIN
  payload = json_build_object(
    'event', TG_OP,
    'incident_id', COALESCE(NEW.incident_id, OLD.incident_id),
    'verification_status', COALESCE(NEW.verification_status::text, OLD.verification_status::text),
    'state', COALESCE(NEW.state, OLD.state),
    'lga', COALESCE(NEW.lga, OLD.lga)
  );
  PERFORM pg_notify('incident_changes', payload::text);
  RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER incidents_notify
  AFTER INSERT OR UPDATE OR DELETE ON incidents
  FOR EACH ROW EXECUTE FUNCTION notify_incident_change();

CREATE OR REPLACE FUNCTION notify_bubble_refresh()
RETURNS TRIGGER AS $$
BEGIN
  PERFORM pg_notify('bubble_refresh', json_build_object(
    'geo_id', COALESCE(NEW.geo_id, OLD.geo_id),
    'level', COALESCE(NEW.level, OLD.level)
  )::text);
  RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER geo_agg_cache_notify
  AFTER INSERT OR UPDATE OR DELETE ON geo_agg_cache
  FOR EACH ROW EXECUTE FUNCTION notify_bubble_refresh();

-- ---------------------------------------------------------------------------
-- Refresh geo_agg_cache from published incidents (reported+)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION refresh_geo_agg_cache()
RETURNS void AS $$
BEGIN
  DELETE FROM geo_agg_cache;

  INSERT INTO geo_agg_cache (
    geo_id, level, name, state, lga, lat, lng, count, intensity, by_type, dominant_verification
  )
  SELECT
    CASE
      WHEN i.lga IS NOT NULL AND i.lga <> '' THEN lower(i.state) || ':' || lower(i.lga)
      ELSE lower(i.state)
    END AS geo_id,
    CASE
      WHEN i.lga IS NOT NULL AND i.lga <> '' THEN 'lga'
      ELSE 'state'
    END AS level,
    COALESCE(NULLIF(i.lga, ''), i.state) AS name,
    i.state,
    NULLIF(i.lga, ''),
    AVG(ST_Y(i.geom::geometry)) AS lat,
    AVG(ST_X(i.geom::geometry)) AS lng,
    COUNT(*)::INT AS count,
    LN(COUNT(*) + 1)::REAL AS intensity,
    jsonb_object_agg(i.event_type::text, type_counts.cnt) FILTER (WHERE type_counts.cnt IS NOT NULL),
    (
      SELECT verification_status
      FROM incidents i2
      WHERE i2.state = i.state
        AND COALESCE(i2.lga, '') = COALESCE(i.lga, '')
        AND i2.published_at IS NOT NULL
        AND i2.verification_status IN ('reported', 'verified', 'official_confirmation')
      GROUP BY verification_status
      ORDER BY COUNT(*) DESC
      LIMIT 1
    )
  FROM incidents i
  LEFT JOIN LATERAL (
    SELECT i.event_type, COUNT(*)::INT AS cnt
    FROM incidents ix
    WHERE ix.state = i.state
      AND COALESCE(ix.lga, '') = COALESCE(i.lga, '')
      AND ix.published_at IS NOT NULL
      AND ix.verification_status IN ('reported', 'verified', 'official_confirmation')
      AND ix.event_type = i.event_type
    GROUP BY i.event_type
  ) type_counts ON true
  WHERE i.published_at IS NOT NULL
    AND i.verification_status IN ('reported', 'verified', 'official_confirmation')
    AND i.geom IS NOT NULL
  GROUP BY i.state, i.lga;
END;
$$ LANGUAGE plpgsql;
