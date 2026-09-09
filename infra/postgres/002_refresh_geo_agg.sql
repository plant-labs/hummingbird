-- Simplified geo aggregation refresh + Nigeria state centroids seed helper

CREATE OR REPLACE FUNCTION refresh_geo_agg_cache()
RETURNS void AS $$
BEGIN
  DELETE FROM geo_agg_cache;

  INSERT INTO geo_agg_cache (
    geo_id, level, name, state, lga, lat, lng, count, intensity, by_type, dominant_verification
  )
  SELECT
    CASE
      WHEN i.lga IS NOT NULL AND btrim(i.lga) <> '' THEN lower(i.state) || ':' || lower(btrim(i.lga))
      ELSE 'state:' || lower(i.state)
    END,
    CASE
      WHEN i.lga IS NOT NULL AND btrim(i.lga) <> '' THEN 'lga'
      ELSE 'state'
    END,
    COALESCE(NULLIF(btrim(i.lga), ''), i.state),
    i.state,
    NULLIF(btrim(i.lga), ''),
    AVG(ST_Y(i.geom::geometry)),
    AVG(ST_X(i.geom::geometry)),
    COUNT(*)::INT,
    LN(COUNT(*) + 1)::REAL,
    (
      SELECT jsonb_object_agg(sub.event_type, sub.cnt)
      FROM (
        SELECT event_type::text AS event_type, COUNT(*)::INT AS cnt
        FROM incidents i2
        WHERE i2.state = i.state
          AND COALESCE(btrim(i2.lga), '') = COALESCE(btrim(i.lga), '')
          AND i2.published_at IS NOT NULL
          AND i2.verification_status IN ('reported', 'verified', 'official_confirmation')
        GROUP BY event_type
      ) sub
    ),
    (
      SELECT verification_status
      FROM incidents i3
      WHERE i3.state = i.state
        AND COALESCE(btrim(i3.lga), '') = COALESCE(btrim(i.lga), '')
        AND i3.published_at IS NOT NULL
        AND i3.verification_status IN ('reported', 'verified', 'official_confirmation')
      GROUP BY verification_status
      ORDER BY COUNT(*) DESC
      LIMIT 1
    )
  FROM incidents i
  WHERE i.published_at IS NOT NULL
    AND i.verification_status IN ('reported', 'verified', 'official_confirmation')
    AND i.geom IS NOT NULL
  GROUP BY i.state, i.lga;
END;
$$ LANGUAGE plpgsql;
