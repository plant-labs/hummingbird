# Hummingbird Methodology Codebook

Hummingbird is an open-source security intelligence platform for Nigeria. This codebook
defines how incidents are collected, coded, verified, and published. Credibility depends
on following these rules; they are product constraints, not guidelines.

## Core principles

1. **Reported ≠ verified.** The same incident record moves through explicit verification
   states. Unverified claims must never appear as flat fact on the live map.
2. **No source, no field.** Every published fact carries a citation (URL, outlet, excerpt,
   timestamp). Fields without a source are rejected.
3. **LLM extracts; it does not invent.** Entity extraction is constrained to structured
   output with a required source-span for every field.
4. **Human review before auto-publish** for casualty and headcount figures, and for any
   record that would appear on the default public map.

## Event types

| Code | Definition |
|------|------------|
| `kidnap` | Abduction or forced disappearance of civilians without further lethal violence in the same report |
| `robbery` | Armed or violent theft targeting civilians or commercial targets |
| `terrorism` | Attacks attributed to organised non-state armed groups targeting civilians or soft targets |
| `protest` | Public demonstration (peaceful or with force used against protesters) |
| `scam` | Organised fraud / advance-fee / impersonation schemes with geographic or mass-victim reporting |
| `battle` | Armed clash between organised groups |
| `explosion` | Remote explosive, IED, or similar attack |
| `other` | Security-relevant event that does not fit the above (must be justified in notes) |

Event definitions are informed by HumAngle Tracker and ACLED coding practice, extended
with **scams** as a first-class Hummingbird type.

## Location coding

- Prefer LGA when named in source; otherwise state-level with `location_precision=state`.
- Exact coordinates only when the source gives a place that can be geocoded confidently;
  otherwise use LGA/state centroid and set precision accordingly.
- Never invent coordinates from narrative alone.

## Victim and casualty coding

- Prefer aggregated `victim_type` (students, travelers, worshippers, etc.).
- **Do not publish victim names or photos** unless officially released by competent
  authorities or next of kin via verified official channels.
- Fatality / casualty and headcount fields **always** require human review before publish.
- When sources disagree on counts, record the range in notes and cite each source; do not
  average silently.

## Verification status

| Status | Rule |
|--------|------|
| `unconfirmed` | Single non-official source, or crowd-only, or incomplete extraction |
| `reported` | ≥2 independent sources **or** 1 official source (police PRO, SEMA, NHRC, etc.) |
| `verified` | Human moderator has approved the record for public map |
| `official_confirmation` | At least one PRO/SEMA/NHRC-class official source confirming core facts |

**Default public map:** `reported` and above only. “Include unconfirmed” is off by default
and must be visually distinct.

## Corroboration

- Independence: same wire rewrite / syndication counts as **one** source family.
- Official sources may short-circuit to `reported` with a single citation.
- Social posts alone never publish to the default map without corroboration or official
  confirmation.
- Crowd submissions never auto-publish alone.

## Incident (release) status lifecycle

Tracked separately from verification. Each transition requires its own source + timestamp.

`ongoing` → `in_negotiation` → `released` | `rescued` | `casualty_confirmed` | `unresolved`

This lifecycle is a primary Hummingbird differentiator: status changes are first-class
history, not overwritten fields.

## Sourcing tiers (reliability)

1. Official government / statutory body
2. Established national investigative outlets
3. Regional / local news
4. Verified NGO / research orgs
5. Social / crowd (highest noise; highest corroboration bar)

## What we do not publish

- Unverified casualty figures on the default map
- Victim identities without official release
- Speculative perpetrator attribution without source span
- Raw unfiltered social firehoses (sources are curated timelines per incident)

## Review workflow

1. Ingest → bronze (raw immutable)
2. Extract + cluster → silver (unpublished candidates)
3. Automated corroboration gates → review queue or gold candidates
4. Human approve / reject / edit → publish to Postgres serving store
5. Status updates append `status_history` with citations; map/SSE refresh

## Comparison note

Hummingbird does not replace HumAngle, SBM Intelligence, Nextier SPD, or ACLED. We
differentiate on near-real-time verification labels, per-field citations, and
release-status tracking. Partnership and methodology transparency matter more than
rebuilding every ingest feed from scratch.
