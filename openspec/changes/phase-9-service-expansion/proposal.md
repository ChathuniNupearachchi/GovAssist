# Phase 9: Service expansion — seven citizen-intent services, general information, photo studios

**Revised twice after user review.** Round 1 corrected two research
gaps (the under-16 branch's sources were re-read and found complete;
the service list was checked against every source in full, not
fragments). Round 2 corrected the organizing principle itself: a
service is what a citizen came in to obtain, not which form implements
it. First-time application and child-name-deletion are their own
services now, not folded into renewal/amendment for sharing paperwork.
See design.md's "Correction record" for both, kept visible rather than
rewritten away.

## Why

Phase 1-8 covers one service (adult passport renewal) plus amendment as
a same-request alternative. Real citizens arrive with seven distinct
things they came in to get, only two of which are built. Building the
rest means reading what the Department's sources actually say for each
one — not assuming from the existing renewal service's shape, and not
organizing around which page or form happens to describe two different
errands together.

## The seven services (full detail, citations, gaps in design.md)

1. **Renew passport** — built; being re-verified against the rebuilt
   model, not re-implemented from scratch.
2. **New passport (first-time)** — same documents/fee/form as renewal,
   different citizen framing and different likely mistakes. Not built.
3. **Replace a lost or stolen passport** — its own documents, a
   penalty fee, a police-report prerequisite. Not built.
4. **Amend an existing passport** — currently only 1 of 7 alteration
   types (`id=10`) is seeded (Change of Name). This phase adds the
   other 5 that remain amendment rows (Profession inclusion, NIC
   inclusion, Cancel Single/India-Nepal journey, Other).
5. **Passport for a child under 16** — fully sourced (two independent
   sources, one more detailed than initially found). Not built; the
   scope gate stays until it is, and tested.
6. **Delete a child's name from a parent's passport** — its own
   errand, LKR 1,200, a form-identity conflict resolved practically
   (recommend the general alteration form, disclose Form I.E. 35C as
   an unconfirmed alternative). Not built.
7. **Emergency Certificate (India and Nepal)** — narrow, real, its own
   fee (LKR 500). Documents/timeline/offices are genuine gaps in the
   sources, not filled in. Not built.

**Not services** (confirmed on the same citizen-intent test, unchanged
from Round 1): urgent one-day service (a `service_basis` modifier —
`id=7` states it plainly as an option within any service, not its own
application) and overseas application through a Mission (a channel
crossing every service — `id=7`/`id=8`/`id=9`/`id=10` all separately
list Overseas Missions as one of several office options for their own
service, not a distinct thing obtained).

**Explicitly excluded, considered not overlooked**: Diplomatic
Passport, Official Passport (both restricted to VVIPs/MPs/officials),
and the Identification Certificate (issued to foreigners, outside
GovAssist's Sri-Lankan-citizen scope).

## General information (design.md's new section)

Nine topics extracted from the sources independent of any one service
— offices/hours, photographs, fingerprints, forms, payment, timelines,
collection, validity, overseas — each cited where the sources answer.
**Five genuine gaps found and left as gaps**: whether an appointment is
needed, how fees are paid and what's refundable, how a finished
passport is collected (SMS? third-party collection?), when to renew
before expiry, and any directory of specific overseas Missions.

## Photo studios — implemented this session, ahead of the rest

`app.ingestion.studio_scraper` scraped all 25 districts from the live
`json/function.php` endpoint (1,420 authorized studios total, verified
directly against the seeded `AUTHORIZED_STUDIO` table) and
`app.engine.studios.resolve_studios` performs the district lookup —
both built and tested independently of the service-list correction
above, since studios aren't scoped to one service; they apply to
whichever service a citizen is pursuing that needs a photo.

## Implementation order (Part 2, once this proposal is agreed)

One service at a time, hardest first while context is freshest, each
step ending in: rules seeded with citations, golden scenarios added,
QA harness run, results reported, before starting the next:

1. Renew (re-verify against the rebuilt model)
2. New passport (first-time)
3. Replace lost/stolen
4. Amend (all alteration types)
5. Passport for a child under 16
6. Delete a child's name
7. Emergency Certificate

## Impact

- New DB rows only for now, not new tables beyond `AUTHORIZED_STUDIO`
  (already migrated) — `passport-new`, `passport-lost-stolen`,
  `passport-under-16`, `passport-child-deletion`, `emergency-
  certificate` join `passport-renewal`/`passport-amendment` as
  sibling `SERVICE` rows, same pattern as amendment alongside renewal
  today.
- `api/app/ingestion/sources.py` — every source URL mapped to the
  service(s) it supports (updated for the corrected 7-service list),
  superseding the scattered `TARGET_PAGES`/`TARGET_PDFS` lists.
- Existing renewal/amendment rule data is not removed — this adds
  sibling services, it does not restructure what's already shipped.

**Not implemented beyond the studio lookup** — this is the read-first-
and-propose step. Rule seeding, golden scenarios, and QA runs follow
per-service, in the order above, once this proposal is agreed.
