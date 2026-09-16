-- Fill null/blank LGA with sentinel so every published incident appears on the LGA map layer.
-- "Unspecified" is self-describing; no separate flag column.

UPDATE incidents
SET lga = 'Unspecified',
    location_precision = 'state',
    updated_at = now()
WHERE lga IS NULL OR btrim(lga) = '';

SELECT refresh_geo_agg_cache();
