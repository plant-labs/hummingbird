# Hummingbird seed: demo published incidents for local map development

INSERT INTO sources (source_id, url, outlet, source_type, fetched_at, reliability_tier, excerpt)
VALUES
  ('11111111-1111-1111-1111-111111111101', 'https://example.com/punch/kaduna-kidnap', 'Punch', 'news', now() - interval '2 days', 2,
   'Gunmen abducted 12 travelers along the Kaduna-Abuja highway.'),
  ('11111111-1111-1111-1111-111111111102', 'https://example.com/dailytrust/kaduna-kidnap', 'Daily Trust', 'news', now() - interval '2 days', 2,
   'At least 12 passengers were kidnapped on the Kaduna-Abuja road.'),
  ('11111111-1111-1111-1111-111111111103', 'https://example.com/premiumtimes/borno-attack', 'Premium Times', 'news', now() - interval '5 days', 2,
   'Residents reported an attack on a community in Borno State.'),
  ('11111111-1111-1111-1111-111111111104', 'https://example.com/police/borno-statement', 'Police PRO Borno', 'official', now() - interval '4 days', 1,
   'Police confirm armed assault in southern Borno; investigation ongoing.'),
  ('11111111-1111-1111-1111-111111111105', 'https://example.com/vanguard/lagos-scam', 'Vanguard', 'news', now() - interval '1 day', 2,
   'Investment scam syndicate defrauded residents in Lagos Island.'),
  ('11111111-1111-1111-1111-111111111106', 'https://example.com/premiumtimes/lagos-scam', 'Premium Times', 'news', now() - interval '1 day', 2,
   'Two outlets report a coordinated crypto investment scam in Lagos.')
ON CONFLICT (url) DO NOTHING;

INSERT INTO incidents (
  incident_id, event_type, date_occurred, date_reported, state, lga, geom,
  location_precision, verification_status, confidence_score, corroboration_count,
  current_status, headline, published_at
) VALUES
  (
    '22222222-2222-2222-2222-222222222201',
    'kidnap', CURRENT_DATE - 3, CURRENT_DATE - 2, 'Kaduna', 'Chikun',
    ST_SetSRID(ST_MakePoint(7.4165, 10.4500), 4326)::geography,
    'lga', 'verified', 0.85, 2, 'ongoing',
    'Travelers abducted on Kaduna-Abuja highway',
    now() - interval '1 day'
  ),
  (
    '22222222-2222-2222-2222-222222222202',
    'terrorism', CURRENT_DATE - 6, CURRENT_DATE - 5, 'Borno', 'Chibok',
    ST_SetSRID(ST_MakePoint(12.8470, 10.8690), 4326)::geography,
    'lga', 'official_confirmation', 0.95, 2, 'unresolved',
    'Armed assault reported in southern Borno',
    now() - interval '3 days'
  ),
  (
    '22222222-2222-2222-2222-222222222203',
    'scam', CURRENT_DATE - 2, CURRENT_DATE - 1, 'Lagos', 'Lagos Island',
    ST_SetSRID(ST_MakePoint(3.4010, 6.4550), 4326)::geography,
    'lga', 'reported', 0.70, 2, 'ongoing',
    'Investment scam syndicate active in Lagos Island',
    now() - interval '12 hours'
  ),
  (
    '22222222-2222-2222-2222-222222222204',
    'robbery', CURRENT_DATE - 4, CURRENT_DATE - 4, 'Rivers', 'Port Harcourt',
    ST_SetSRID(ST_MakePoint(7.0130, 4.8156), 4326)::geography,
    'lga', 'reported', 0.65, 2, 'unresolved',
    'Armed robbery along Port Harcourt arterial road',
    now() - interval '2 days'
  ),
  (
    '22222222-2222-2222-2222-222222222205',
    'kidnap', CURRENT_DATE - 10, CURRENT_DATE - 9, 'Zamfara', 'Anka',
    ST_SetSRID(ST_MakePoint(5.9500, 12.1100), 4326)::geography,
    'lga', 'verified', 0.80, 3, 'released',
    'Villagers kidnapped in Anka LGA later released',
    now() - interval '4 days'
  )
ON CONFLICT (incident_id) DO NOTHING;

INSERT INTO incident_sources (incident_id, source_id, role) VALUES
  ('22222222-2222-2222-2222-222222222201', '11111111-1111-1111-1111-111111111101', 'primary'),
  ('22222222-2222-2222-2222-222222222201', '11111111-1111-1111-1111-111111111102', 'corroborating'),
  ('22222222-2222-2222-2222-222222222202', '11111111-1111-1111-1111-111111111103', 'primary'),
  ('22222222-2222-2222-2222-222222222202', '11111111-1111-1111-1111-111111111104', 'corroborating'),
  ('22222222-2222-2222-2222-222222222203', '11111111-1111-1111-1111-111111111105', 'primary'),
  ('22222222-2222-2222-2222-222222222203', '11111111-1111-1111-1111-111111111106', 'corroborating'),
  ('22222222-2222-2222-2222-222222222204', '11111111-1111-1111-1111-111111111101', 'primary'),
  ('22222222-2222-2222-2222-222222222204', '11111111-1111-1111-1111-111111111102', 'corroborating'),
  ('22222222-2222-2222-2222-222222222205', '11111111-1111-1111-1111-111111111102', 'primary'),
  ('22222222-2222-2222-2222-222222222205', '11111111-1111-1111-1111-111111111103', 'corroborating')
ON CONFLICT DO NOTHING;

INSERT INTO incident_fields (incident_id, field_name, value_json, source_id, source_span, confidence) VALUES
  ('22222222-2222-2222-2222-222222222201', 'victim_count', '12', '11111111-1111-1111-1111-111111111101',
   'Gunmen abducted 12 travelers along the Kaduna-Abuja highway.', 0.9),
  ('22222222-2222-2222-2222-222222222201', 'victim_type', '"travelers"', '11111111-1111-1111-1111-111111111101',
   'Gunmen abducted 12 travelers along the Kaduna-Abuja highway.', 0.85),
  ('22222222-2222-2222-2222-222222222203', 'victim_type', '"residents"', '11111111-1111-1111-1111-111111111105',
   'Investment scam syndicate defrauded residents in Lagos Island.', 0.8),
  ('22222222-2222-2222-2222-222222222205', 'victim_count', '8', '11111111-1111-1111-1111-111111111102',
   'Eight villagers were kidnapped in Anka and later released.', 0.75)
ON CONFLICT DO NOTHING;

INSERT INTO status_history (incident_id, from_status, to_status, changed_at, source_id, note) VALUES
  ('22222222-2222-2222-2222-222222222201', NULL, 'ongoing', now() - interval '2 days',
   '11111111-1111-1111-1111-111111111101', 'Initial report'),
  ('22222222-2222-2222-2222-222222222205', NULL, 'ongoing', now() - interval '9 days',
   '11111111-1111-1111-1111-111111111102', 'Initial abduction report'),
  ('22222222-2222-2222-2222-222222222205', 'ongoing', 'released', now() - interval '4 days',
   '11111111-1111-1111-1111-111111111103', 'Victims reported released');

INSERT INTO review_queue (queue_id, incident_id, candidate_json, status, priority, reason)
VALUES (
  '33333333-3333-3333-3333-333333333301',
  NULL,
  '{"event_type":"protest","state":"Oyo","lga":"Ibadan North","headline":"Protest over insecurity in Ibadan","corroboration_count":1}'::jsonb,
  'pending',
  50,
  'Single source — needs corroboration or moderator decision'
)
ON CONFLICT DO NOTHING;

SELECT refresh_geo_agg_cache();
