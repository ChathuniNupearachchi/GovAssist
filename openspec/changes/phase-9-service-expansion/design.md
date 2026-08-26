## Correction record (read before anything else)

Two rounds of user review corrected this document. Both are kept here,
not silently folded in:

**Round 1** — the under-16 branch was wrongly reported as unsourced
(section (c) of `instructions_english_td.pdf`, already ingested, was
never actually re-read); the 10-year validity fee tier was wrongly
reported as unconfirmed (visible in `id=8`, not read fully). Both
corrected; see git history / the conversation record for the original
text.

**Round 2** — the service list itself was organized wrong. First-time
application was folded into renewal as a `holds_passport_reason` value
because the paperwork is nearly identical; child-name-deletion was
folded into amendment because it shares a form and fee. Both wrong for
the same reason: **a service is defined by what a citizen came in to
obtain, not by which form implements it or which table row describes
it.** A first-time applicant and a renewer share paperwork but not an
errand — different knowledge, different anxieties, different likely
mistakes. A parent removing a child from their passport is a distinct
thing they want done, even though it happens to cost the same and use
adjacent forms as other alterations. This document is rewritten below
on that principle. Two things from Round 1's list were confirmed
correct on that same test — urgent service and overseas application
are genuinely modifiers/channels, not things a citizen "comes in to
obtain" in their own right — and are unchanged.

## Context

Manual QA (the bug-fix round) surfaced six defects in the existing
renewal service. This proposal expands scope to the situations that
service round didn't cover, built only from what the Department's own
pages and forms actually say — checked against the live database
before any of it was assumed, twice now.

### Ingestion state (unchanged from Round 1, still accurate)

`id=7`, `id=8`, `id=9`, `id=10` ingested and approved; `id=11`
deliberately not ingested (its content is duplicated verbatim inside
`id=9`); `id=12`, the two new PDFs, and the studio endpoint were not
ingested at the start of this work. **The studio endpoint now is** —
scraped and seeded during this session (1,420 rows across all 25
districts, via `app.ingestion.studio_scraper`, verified directly
against the live `AUTHORIZED_STUDIO` table). `id=12` and the two PDFs
remain un-ingested pending the per-service implementation order below.

## The service list, rebuilt around citizen intent

Seven services. For each: the citizen's own likely words, eligibility,
the full document set (conditional items marked), fee (with
penalties/tiers), timeline, offices, prerequisite order, the form and
where to get it, and common misrouting — sourced, with gaps stated as
gaps rather than filled in.

### 1. Renew passport

**Citizen's words**: "my passport expired", "I need to renew my
passport", "my passport is expiring soon."

**Eligibility**: a Sri Lankan citizen who already holds (or held) an
ordinary all-countries passport that is expired, expiring, or damaged
— not lost or stolen (service 3) and not a first application
(service 2). (`id=7` seq 5: "A Sri Lankan Citizen by descent or by
registration.")

**Documents** (`id=8` seq 3-4): current passport + photocopy of the
bio-data page; photo studio acknowledgement; original birth certificate
+ photocopy; original NIC + photocopy; marriage certificate + photocopy
*where necessary* (to confirm a name after marriage); educational
certificate + a document confirming service, *related to profession*
(conditional — only if profession is stated). Buddhist priests
additionally: Samanera or Higher Ordination certificate + photocopy.

**Fee** (`id=8` seq 9): Normal LKR 10,000 / Urgent LKR 20,000.

**Timeline** (`id=8` seq 8): Normal 30 working days / Urgent same day.

**Offices** (`id=8` seq 6-7): Head Office (Battaramulla); Regional
Offices — Kandy, Matara, Vavuniya, Kurunegala, Jaffna; Divisional
Secretariat (form pickup only — never submission, per this project's
existing `Requirement.freshness_rule` note); Overseas Sri Lankan
Missions.

**Prerequisite order**: photo via an authorized studio (produces the
studio acknowledgement, a required document) before applying;
fingerprints (age 16-60) captured in person at Head Office or a
Regional Office (`id=7` seq 13) — not a document to bring, an in-person
step at submission.

**Form**: K-35A (`passport_application.pdf`, already ingested).

**Common misrouting**: a citizen whose passport was lost or stolen
(service 3) or who has never held one at all (service 2) may describe
either as "I don't have my passport" — the reason question distinguishes
these before routing.

### 2. New passport (first-time applicant)

**Citizen's words**: "I've never had a passport", "applying for my
first passport", "I need a passport for the first time."

**Eligibility**: same citizenship basis as renewal (`id=7` seq 5); no
prior Sri Lankan passport to submit.

**Documents**: the same core set as renewal, minus the current-passport
item (there isn't one — `id=8`'s own asterisk note, "*If you already
have a valid passport it should be submitted along with the
application," implies its absence is expected and not a blocker for a
first-time case). NIC is conditional on age: "All applicants above the
age of 16 years should produce their National Identity Card"
(`instructions_english_td.pdf` (5)) — a first-time applicant under 16
without an NIC yet is not the same document gap as an adult who simply
doesn't have one; this project's existing renewal service doesn't
currently model that distinction either, worth carrying into whichever
service actually implements it. Photo studio acknowledgement,
birth certificate, marriage/profession documents where applicable, and
the Buddhist-priest documents — same as renewal, same sources.

**Fee/Timeline/Offices/Form**: identical to renewal — `id=8`'s "Issue
of Passports... Passports Valid for All Countries" fee/timeline/office
table does not distinguish first-time from renewal at all; the
difference this proposal is building is entirely about *how the
citizen is met* (their own framing, their own likely uncertainty), not
a different fee or form.

**Prerequisite order**: same as renewal.

**Common misrouting**: a citizen who actually held a passport that
expired years ago sometimes describes their situation as "I don't have
a passport" (meaning "not currently, it lapsed") — the reason question
(`holds_passport` → `never_held` / `expired_or_damaged` / `lost_or_
stolen`) distinguishes this from a genuine first-time case before
routing here vs. to renewal.

### 3. Replace a lost or stolen passport

**Citizen's words**: "my passport was stolen", "I lost my passport",
"someone stole my bag with my passport in it."

**Eligibility**: a Sri Lankan citizen whose previously-issued passport
is lost or stolen, domestically or abroad.

**Reporting prerequisite, before any replacement application**
(`id=12`): **domestic** — call the Department's hotline (0112 101 533,
fax 011-2885358, 8.30am-4.00pm Mon-Fri excluding government holidays)
**and** file a police complaint "as soon as possible" (Conflict 1,
RESOLVED — id=12's own numbered steps list both sequentially, not as
alternatives). **Overseas** —
police report from the local police in the country of residence, plus
the complaint-form PDF, submitted together to the nearest Sri Lankan
Diplomatic/Consular office.

**Documents for the replacement passport** (`id=8` seq 32-34,
`instructions_english_td.pdf` (e)): original police complaint,
including the lost passport number (obtainable from the Colombo Head
Office or a Regional Office if unknown); if lost abroad, the temporary
travel document (NMRP) used to re-enter Sri Lanka, with a photocopy.
**Not explicitly restated for this case, but reasonably the same base
application set as renewal/new** (photo studio acknowledgement, birth
certificate, NIC, etc.) since the outcome is a fresh passport — this
is an inference from the general Ordinary Passport document list, not
a lost-passport-specific citation, and should be confirmed rather than
assumed correct during implementation.

**Fee**: the normal/urgent base passport fee (10,000/20,000) **plus** a
penalty — Rs 20,000 if lost within one year of issue, Rs 15,000 if lost
after one year (charged only if the passport's validity period had not
already lapsed) (`id=8` seq 33-34).

**Timeline**: not explicitly restated for this case in any source read
— reasonably the same as renewal (30 days/same-day) but **unconfirmed,
flagged as a gap**.

**Offices**: domestic — police station, then Head Office/Regional
Office for the replacement application; overseas — the Diplomatic/
Consular Mission.

**Prerequisite order**: (1) police report (+ hotline call, domestically)
→ (2) if abroad, obtain the NMRP from the Mission first (needed to
travel back to Sri Lanka at all) → (3) apply for the replacement
passport with the police complaint (+ NMRP if applicable).

**Form**: the complaint-form PDF for the overseas path (has a proper
download URL, extracted cleanly — has a text layer); no separate
Department complaint form found for the domestic path (the police's own
complaint document, not a Department form, is what's produced there);
the replacement application itself uses K-35A, same as renewal.

**Common misrouting**: a citizen whose passport merely expired,
described loosely as "I lost my passport" (meaning "I don't have a
valid one"), needs the reason question to route correctly to renewal
instead.

### 4. Amend an existing passport

**Citizen's words**: "I need to change my name on my passport", "add
my profession to my passport", "update my NIC number on my passport."

**Eligibility**: any current Sri Lankan passport holder (`id=10` seq 2:
"A Sri Lankan passport holder may apply for amendments of the data
included in his/her passport").

**Alteration types, all flat LKR 1,200** (`id=10` seq 6) — only Change
of Name currently built; this phase's job is the rest:

| Alteration | Documents required |
|---|---|
| Change of Name | Passport & Birth Certificate or Marriage Certificate where applicable |
| Profession inclusion | Documents and qualification to prove profession |
| NIC Number Inclusion | National Identity Card |
| Cancel Single Journey | National Identity Card and Birth certificate |
| Cancel India Nepal only | National Identity Card and Birth certificate |
| Other Amendments | (unspecified in the source) |

(Deletion of a child's name is *not* listed here — see service 6.)

**Timeline** (`id=10` seq 5): 1 hour 30 minutes — dramatically faster
than a full passport, worth stating plainly to a citizen who might
assume amendment takes as long as renewal.

**Offices** (`id=10` seq 3-4): Head Office (Colombo/Battaramulla),
Regional Offices (5), Overseas Sri Lankan Missions.

**Prerequisite order**: must already hold the passport being altered.

**Form**: the general Alteration Application Form (`amendment.pdf`,
already ingested).

**Common misrouting**: amendment only changes data on an existing valid
passport — a citizen with a lost, stolen, or badly damaged passport
needs services 3 or 1, not amendment.

### 5. Passport for a child under 16

**Citizen's words**: "applying for my child's first passport", "my son
needs a passport", "how do I get a passport for my daughter."

**Eligibility**: any Sri Lankan citizen under 16 — mandatory separate
passport; inclusion in a parent's passport is no longer permitted at
all (`id=7` seq 3/14, `id=8` seq 30 — both state this plainly and
independently).

**Both parents, or the legal guardian, must attend and hand over the
application** (`instructions_english_td.pdf` (c)(x); `id=8` seq 23).

**Documents** (`instructions_english_td.pdf` section (c), full text
quoted in Round 1's correction; `id=8` seq 23-27, an even fuller
treatment): Form K-I.E. 35(A); original birth certificate + photocopy
(an English translation is explicitly **not** accepted as the
original); photocopies of both parents' passport data pages + the page
showing the child's particulars, or NICs if a parent has no passport;
letters of consent from parents (Mission-endorsed if either or both are
abroad); death certificate if a parent is deceased; certified divorce
certificate if parents are divorced; **child-name-deletion first, as a
prerequisite, if the child was previously included in a parent's
passport** (routes to service 6 before this service can proceed);
citizenship certificate if the child was born overseas; photo studio
acknowledgement; current passport if available. Special circumstances
from `id=8`: affidavit + NIC if a parent lacks a valid passport;
Grama-Niladhari report (attested by the Divisional Secretary) plus
Guardian ID and consent letter if a parent is deceased; police report
copy + Grama-Niladhari confirmation (countersigned by the Divisional
Secretary) if the child was abandoned. Adopted child, additionally:
Certificate of Adoption, the court order, a letter from the
Commissioner of Probation and Child Care.

**Fee** (`id=8` seq 28-29) — the citizen/parent chooses the validity
tier: 3-year validity — Normal LKR 3,000 / Urgent LKR 9,000; 10-year
validity — Normal LKR 10,000 / Urgent LKR 20,000.

**Timeline/Offices**: not explicitly restated for the minor case
specifically in any source read — reasonably the same as the adult
process, **flagged as unconfirmed** rather than assumed.

**Form**: K-I.E. 35(A) — same form number as the adult application,
confirmed by `instructions_english_td.pdf` section (a)'s own heading
covering "the application K - I.E. 35 A" generally, with point (19)
specifically addressing "the father or guardian... if the application
is of a child less than 16 years of age."

**Prerequisite order**: if the child was previously listed in a
parent's passport, service 6 (deletion) must be completed first.

**Common misrouting**: a parent might ask to simply "add" or "include"
their child on their own passport — this is not offered at all
anymore (confirmed independently by two sources) and must be stated
plainly, not answered as if it were still possible.

### 6. Delete a child's name from a parent's passport

**Citizen's words**: "remove my child from my passport", "I need to
take my daughter off my passport", "my son needs his own passport now,
how do I delete him from mine."

**Eligibility**: a parent whose passport currently lists a child —
necessarily an older passport, since this practice ended (see service
5); a parent with a passport issued under the current rules would never
have had a child listed to begin with.

**Fee**: LKR 1,200 — confirmed by two independent sources agreeing:
`id=10`'s alteration table ("Deletion of a child's name | Passport |
LKR 1,200.00") and `instructions_english_td.pdf` (c)(viii) ("The form
I.E. 35C should be filled and a fee of Rs.1,200 will be charged").

**Form — Conflict 3, UPDATED with `id=24` evidence (Downloads-page
re-verification), still open**: `id=10` names the *general* Alteration
Application Form (`amendment.pdf`, unambiguously sourced, already
ingested, already used for every other alteration type).
`instructions_english_td.pdf` separately names "Form I.E. 35C," and the
fetched `child_deletion_application.pdf` ("APPLICATION FOR DELETION OF
CHILDREN") references "form 35C" in its own (partially garbled) OCR'd
text without confirming it's the identical document.

`id=24` (the Downloads page, ingested this session) is now the
strongest evidence yet: its Forms table lists "Amendments &
Alterations" / **"Form O"** downloading `amendment.pdf`, and
"Children Deletion" / **"Form C"** downloading
`child_deletion_application.pdf` — as two SEPARATE line items with
distinct form codes, and the site's own designated download for
child-name-deletion is the dedicated file, not the general alteration
form. This is direct, sourced confirmation that child-name-deletion
has its own designated form — the recommend-the-general-form-and-
disclose-an-alternative resolution below is now superseded by this
stronger evidence, not merely elaborated on.

**Still NOT established**: whether "Form C" (`id=24`'s label) and
"Form I.E. 35C" (`instructions_english_td.pdf`'s label) are the same
document. `id=24` never uses the "I.E. 35C" label anywhere on the page
— it only ever calls the file "Form C". No source read for this phase
states the identity either way; it remains a real, open gap, now much
better evidenced on the "these are two separate forms" half of the
question, not the "are C and I.E. 35C the same" half.

**Revised recommendation** (supersedes the prior one — the general
`id=10` alteration form is no longer recommended for this alteration
type): when `passport-child-deletion` is built, its form Requirement
should cite `child_deletion_application.pdf` ("Form C") directly, not
`amendment.pdf` ("Form O") — `app.ingestion.sources.py`'s
`amendment.pdf` entry has already dropped `passport-child-deletion`
from its `service_codes` to reflect this. Disclosing "Form I.E. 35C" as
a related, unconfirmed-identical label is still worth keeping in the
requirement's detail text, since a citizen may see that label used at a
counter or on the instructions PDF and should not be confused into
thinking it's a third, different form. This reasoning belongs in the
requirement's own detail text at implementation time
(`Requirement.freshness_rule` or equivalent), not only in a citation —
per explicit instruction, because filing the wrong form risks the
application being rejected, a higher-stakes error than the office/
fingerprint conflicts (which are informational, not filing-critical).
Not yet implemented — `passport-child-deletion` itself isn't built
(see Implementation order); this is a design record for when it is.

**Timeline**: not separately restated for this specific alteration type
— reasonably the same 1h30m as every other alteration (`id=10` seq 5
states this for "Alterations" generally, and this is one row of that
same table), but not independently confirmed for this row specifically.

**Offices**: same as amendment (service 4) — Head Office, Regional
Offices, Overseas Missions.

**Prerequisite relationship**: this service is itself often a
prerequisite step *before* service 5 (a child's own new passport), not
only a standalone errand — a parent may arrive already knowing they
need "the deletion thing" specifically because service 5 sent them here
first.

**Common misrouting**: a parent might describe this generically as "an
amendment" without realizing it's is own recognizable errand with its
own form question — worth naming explicitly in the general amendment
conversation ("would you like to change a name, or remove a child from
your passport?") rather than only reachable by a citizen already using
the word "delete."

### 7. Emergency Certificate (India and Nepal)

**Citizen's words**: "I need an emergency certificate for Nepal",
"going to India on pilgrimage, what travel document do I need."

**Eligibility**: Buddhist pilgrims traveling specifically to India or
Nepal (`id=7` seq 9: "Emergency Certificates for Buddhist Pilgrims
travel India and Nepal").

**Fee** (`instructions_english_td.pdf` (f)(ii)): LKR 500 normal; no
urgent tier listed (shown as "–"); no separate child tier listed.

**Documents**: **not itemized anywhere read** — genuine gap, not
filled in. The only concrete link found is that "Emergency Certificates
(India and Nepal)" is one of the tick-box travel-document types on the
same K-35A form (`instructions_english_td.pdf` (a)(2)(ii)), implying
the same base application applies, but no source states a document list
specific to this certificate the way it does for the other services.

**Timeline/Offices**: **not stated anywhere read** — genuine gaps.

**Form**: K-35A (same form, different tick-box selection), per the
citation above.

**Common misrouting**: a citizen wanting a full ordinary passport for
travel to India/Nepal might not realize this narrower, cheaper document
exists for pilgrimage specifically; conversely, a citizen might
mistakenly think this document works for travel beyond India/Nepal,
which it explicitly does not.

## Modifiers and channels (not services — confirmed correct from Round 1)

- **Urgent (one-day) service** — a `service_basis` modifier across
  services 1, 2, 3 (presumably — unconfirmed for 3, see above), and 5.
  **Not available** for service 7 (Emergency Certificate — fee table
  shows no urgent tier) and **does not apply the same way** to service
  4/6 (amendment/deletion already has its own fixed 1h30m timeline,
  not a normal/urgent choice).
- **Overseas application** — the Mission channel (`id=9`), crossing
  every service that has an Overseas Missions office option (services
  1, 2, 3, 4, 6 all list it; services 5 and 7 don't explicitly restate
  it, flagged above as unconfirmed for the minor case specifically).

## Out of scope — confirmed correct, recorded with reasoning

- **Diplomatic Passport** (`id=8` seq 10-15) — eligibility restricted
  to VVIPs, Members of Parliament, and persons posted to prescribed
  overseas positions, gated by a Circular this project has not
  ingested. Not a situation an ordinary citizen using GovAssist would
  have.
- **Official Passport** (`id=8` seq 16-21) — restricted to Provincial
  Council members, Mayors, Chairpersons of Local Government Bodies,
  Officers of All Island Services, identified MP staff — same
  reasoning.
- **Identification Certificate** (`id=8` seq 23) — explicitly "issued
  to a foreigner whose passport or travel document has been lost,
  stolen or expired whilst in Sri Lanka" — a non-citizen service,
  outside CLAUDE.md's stated scope ("a Sri Lankan citizen's specific
  government service situation").

All three considered and deliberately excluded, not overlooked.

## Conflicts — all three kept surfaced with citations, not resolved into a single answer

1. **Hotline vs. police complaint** (domestic lost-passport reporting)
   — RESOLVED during service #3's implementation: `id=12`'s own text is
   a numbered instruction list — "1. ...report the incident by phone to
   immigration Department hotline... 2. Make a complaint to your local
   police station as soon as possible" — two sequential steps, not
   alternatives. Read directly (not assumed) once `id=12` was actually
   ingested (it had only been read manually during the original
   research pass, not stored). `id=8`'s replacement-document list
   naming only the police complaint doesn't contradict this — `id=8` is
   about what to BRING to the replacement application (the complaint,
   the artifact the hotline call itself doesn't produce), not the full
   reporting procedure; `id=12` is the fuller procedure. Encoded in
   `app.seed.phase9_lost_stolen` as one combined "report the loss"
   prerequisite naming both steps.
2. **Fingerprint office list** — domestic list includes Jaffna
   (`id=8`); the overseas-applicant fingerprint procedure's list
   (`id=9`) does not. Unresolved — could be a real capability
   difference, not assumed to be a site error.
3. **Which form implements child-name deletion** — resolved
   *practically* (recommend `id=10`'s general form, disclose Form
   I.E. 35C as an unconfirmed alternative — see service 6 above) but
   the underlying fact (are these the same document?) remains
   genuinely unknown and is not asserted either way.

## General information — not tied to one service

Extracted while reading every source above; cited where the sources
answer, flagged as a gap where citizens plainly would ask and nothing
answers.

### Offices and hours

Head Office: "Suhurupaya", Battaramulla (`id=8` seq 6, `id=12`'s
mailing address). Hours (`id=7` seq 6-8): Head Office — one-day service
7.00am-1.30pm, normal service 8.00am-1.30pm, online-application-issues
counter 8.00am-12noon, all on weekdays; Regional Offices — one-day
service from 7.30am, normal service after 12.30pm up to 4.00pm,
weekdays. Closed weekends and public holidays. Divisional Secretariat
offices: form pickup only, never a submission location (established in
this project's existing data, reconfirmed by `id=8` seq 6 listing it
under "where to obtain an application form," never under "where to
submit"). **Appointments: not mentioned in any source read — genuine
gap.** Citizens plainly ask this; the corpus is silent.

### Photographs

Digital only, via an authorized studio — no printed photographs
accepted (`id=7` seq 4/12). The studio transmits the photo online and
issues an acknowledgement note, which must be submitted with the
application. Photos are valid for 6 months. The authorized list is
published in newspapers, on the website, and at District/Divisional
Secretariat offices (`id=7` seq 12) — now also directly queryable by
district via `AUTHORIZED_STUDIO` (1,420 rows, all 25 districts, scraped
and seeded this session from the live `json/function.php` endpoint).

### Fingerprints

Mandatory for every applicant aged 16-60 (`id=7` seq 13, citing Act
No. 20 of 1948 as amended by Act No. 7 of 2015), captured in person at
the Head Office or a Regional Office — never remotely, never via a
document. Overseas applicants: captured on first return to Sri Lanka
after 1 Jan 2018 via a port-of-entry Biometric Data Acquisition form,
then an in-person visit to Head Office or a Regional Office (Matara/
Kandy/Vavuniya/Kurunegala — Jaffna absent, see Conflict 2), ~30-45
minute wait (`id=9`).

### Forms

K-35A for ordinary/new/renewal/minor passports and Emergency
Certificates (same form, different tick-box — `instructions_english_
td.pdf` (a)(2)); the general Alteration form for every amendment
including (recommended) child-name deletion; the complaint-form PDF
for overseas lost/stolen reporting. Hard copies obtainable from the
Head Office, the 5 Regional Offices, District/Divisional Secretariat
offices, or downloaded from the website (`id=7` seq 11, `id=8` seq 6).
**Whether the form must be completed in English specifically: not
stated in any source read.** The Client Undertaking Section on K-35A
must be signed, "no application will be accepted without" that
signature (`id=9`) — that much is confirmed; a language requirement for
the form's other fields is not.

### Payment

**Not addressed in any source read** — how fees are paid (cash, card,
online) and what, if anything, is refundable are both genuine gaps.

### Timelines

Normal 30 working days / urgent same day for a full passport (`id=8`
seq 8); 1h30m for any alteration (`id=10` seq 5). "30 working days" is
reasonably read against the stated weekday-only, holiday-excluded
office hours (`id=7` seq 8), but no source spells out the definition
explicitly — a reasonable inference, not a direct citation.

### Collection

**Partially answered, Downloads-page re-verification**:
`CourierSriLankanPassports.pdf` ("Application to Courier Sri Lankan
Passports", ingested this session) confirms a courier-delivery option
exists as a separate application — fields for the applicant's name/
passport number, reason to courier, name of the courier service, the
relevant foreign Mission/consulate, and destination. This resolves the
narrow question ("is there any delivery option at all?") but the
broader gaps remain: whether SMS notification is used, whether someone
else may collect in person on the applicant's behalf, and — for the
courier option specifically — its fee and eligibility, which aren't
legible in what was extracted (see the extraction-quality note below).
Still a genuine gap on those points, now a narrower one.

**Extraction quality caveat**: `pdfplumber` returned this PDF's text
with every line character-reversed (`"NOITARGIME"` for `"EMIGRATION"`,
etc.) — a PDF text-encoding artifact (reversed glyph run order), not a
scanned-PDF OCR problem, and not one the free OCR chain would fix (it's
not an image). Readable by a human manually reversing each line (done
for this report); NOT re-extracted into clean form this pass, so the
stored `DocumentChunk` text is citation-poor — flagged rather than
silently treated as good RAG-retrievable text. A future pass should
either post-process pdfplumber's output for this specific PDF or route
it through the vision OCR stage despite having a text layer.

### Validity

Ordinary ("N series") passports: 10 years unless otherwise specified
(`id=7` seq 5). Minors: 3 or 10 years, at the parent's choice (`id=7`
seq 5, `id=8`'s two fee tables). Emergency Certificates: 2 years,
extendable by a further 2 (`id=7` seq 5). NMRP/Temporary Travel
Document: one-way travel to Sri Lanka only (`id=8` seq 21). **When a
citizen should renew before expiry — not addressed anywhere read.**

### Overseas

Fully covered under service-crossing "channel" above and `id=9`'s own
content. **No directory of specific Missions/countries is available in
the ingested corpus** — sources say only "the Sri Lankan Mission in
that country, or the nearest one if none is available in-country,"
never a list.

### Downloads page (`pages_e.php?id=24`) — ingested this session

Never previously ingested. Resolves or narrows several open items above
(Conflict 3, Collection); also the source for the intake-ordering
change and printing requirement below. Every PDF it links that this
project didn't already have was ingested and read — findings below,
reported before any condition was encoded, per explicit instruction.

**Intake ordering**: `applying_from` moved to sequence 2 (right after
`age`), ahead of `holds_passport` and everything else —
`app.engine.renewal_intake`. It closes off more branches than any other
question except `age`: which application-form Requirement applies
(domestic K-35A vs. the Overseas Missions form, this section), which
offices accept the application, whether fingerprints happen at intake
or on first return to Sri Lanka (`id=9`, already noted above), and
whether `service_basis` (urgent/normal) is even meaningful — `id=24`
adds no evidence either way on that last point, so it's still asked
unconditionally (see the "service_basis deliberately left ungated"
comment in `app.seed.phase4_renewal`). `age` stays first regardless —
it gates the under-16 scope check, a hard stop that has to run before
anything else.

**Printing requirement**: `id=24`'s own note, verbatim in substance:
"Downloaded forms should be Laser printed in Paper Size A4." Added to
every Requirement in this seed that offers a downloadable form
(domestic K-35A, both variants, and the Overseas Missions form below).

**Second domestic form**: `id=24`'s Forms table lists two K-35A
downloads under different "Downloadable Format" labels —
`passport_application.pdf` ("Online Fill and Printable Travel Document
Application," already the only one this project served) and
`application.pdf` ("Downloadable Travel Document Application," not
previously ingested). Read directly: same fields as the first (NIC,
surname, DOB, birth certificate, profession, dual-citizenship Y/N,
declaration) — a citizen without a computer to fill the online variant
still has a usable path. Neither PDF's own text states "for
handwriting" in so many words; that's a reasonable inference from the
"Downloadable" vs. "Online Fill" labels, not asserted as a directly
sourced fact — both are now offered, labeled with `id=24`'s own column
headers rather than this project's guess at the difference.

**Overseas Missions form set**: `id=24`'s "Overseas Missions" section
lists a main application PLUS five conditional annexes. All six PDFs
were ingested and read (`app.ingestion.phase9_downloads`) — findings
below, from each document's own body text, not guessed from its title:

- **Main form** (`new_om_application_form.pdf`, still labeled "Form
  K-35A") — a DIFFERENT PDF from the domestic K-35A variants. Its own
  extracted text covers a child under 16 on the SAME form (fields 18+:
  "If this application is for a child below the age of 16 years,
  following information must also be provided" — father/guardian and
  mother/guardian NIC fields) and an Emergency/Identity Certificate
  application (form header: "APPLICATION FOR A SRI LANKAN PASSPORT,
  EMERGENCY/IDENTITY CERTIFICATE"). Encoded as `passport-renewal`'s
  overseas form Requirement now (gated on `applying_from == "abroad"`);
  the under-16/Emergency-Certificate coverage is noted in
  `app.ingestion.sources.py` for when those services are built, not yet
  encoded as a Requirement anywhere.
- **Annex i — "Certificate to prove Sri Lankan Citizenship"**: not a
  form to fill — a checklist of which existing certificate qualifies
  (Dual Citizenship Certificate; Overseas Birth Registration
  Certificate; citizenship registration under Citizenship Act sections
  8/11/12/13; a citizenship grant to an Indian- or Chinese-origin
  person). Trigger, from the document's own content: needed by an
  overseas applicant whose citizenship was established through one of
  these routes, not by birth with an ordinary existing Sri Lankan
  passport.
- **Annex ii — "Affidavit not obtain citizenship"**: an affidavit
  declaring the applicant currently holds Indefinite Leave to Remain/
  Settlement/Permanent Residence/Indefinite Leave to Enter in their
  country of residence, and has NOT obtained that country's (or any
  other's) citizenship, asylum, or refugee status. Trigger: an overseas
  applicant with PR/settlement status abroad specifically — distinct
  from annex v, which is about a citizenship-registration route, not
  residency status.
- **Annex iii — "Parent's Consent Letter"**: CONFIRMED identical in
  content to `request_letter.pdf` (item 6 below) — same trilingual
  "Request to issue a separate passport to child" text, same character
  count once extracted, different underlying PDF bytes (republished
  under two URLs/labels). Trigger: a parent/guardian consenting to
  their child receiving their OWN separate passport rather than being
  endorsed on a parent's. Confirms an overseas Mission accepts a
  minor's application at all — see "Flag for later" below.
- **Annex iv — "Lost or Stolen passport complaint form"**: matches its
  title — "This form to be used by Sri Lankans abroad in case of stolen
  or lost passport," submitted with a local Police Report to the
  nearest Sri Lankan Diplomatic Mission; accepting the complaint
  immediately cancels the passport worldwide. UPDATE (service #3's
  implementation): CONFIRMED word-for-word identical in extracted text
  to the already-catalogued `complaint_form%20_stolen_and_lost_sri%20
  lankan_passport.pdf` (Conflict 1) — different bytes/path (this one
  lives under `om/`), same document, both ingested and compared
  directly. Also confirms there is NO separate Department complaint
  FORM for the domestic path — this one PDF, however published, is
  explicitly overseas-only per its own text; the domestic path produces
  the police's own report, not a Department form.
- **Annex v — "Affidavit for Citizenship Declaration"**: its own text —
  "AFFIDAVIT FOR CITIZENSHIP DECLARATION UNDER SECTION 5(2) OF THE
  CITIZENSHIP ACT" — for an applicant whose birth was registered under
  section 5(2) of the Ceylon Citizenship Act (citizenship by descent,
  born abroad to a Sri Lankan parent), declaring they wish to retain
  Sri Lankan citizenship and haven't obtained any other. Trigger:
  specifically a section-5(2)-registered citizen — narrower than, and
  different from, annex ii's PR/settlement trigger, and a different
  section of the Citizenship Act from `section_19_2` (already asked in
  this intake, about the special-provisions dual-citizenship route).

**Not encoded as Requirements yet**: none of the five annexes are
added to `passport-renewal`'s Requirement set. Annexes iii and iv don't
apply to an adult renewal at all (they belong to the not-yet-built
under-16 and lost-stolen services). Annexes i/ii/v's real trigger
conditions depend on facts this intake doesn't collect for any service
— which certificate type established citizenship, PR/settlement status
abroad, or section-5(2) registration specifically — and inventing a
new intake question for each wasn't asked for and risks guessing at
how common each case actually is. Showing all three unconditionally to
every overseas renewal applicant would be exactly the "wrong checklist
is worse than no checklist" failure CLAUDE.md warns against, so this is
left as a documented gap rather than guessed.

**Flag for later** (item 9): annex iii's existence — a parent's consent
letter specifically for a child receiving a separate passport through
an Overseas Mission — implies the minor-and-overseas combination is
handled at all, which isn't obvious from `id=9`'s general overseas
procedure or `id=8`'s minor section read independently. When
`passport-under-16` is built, check explicitly whether "minor +
applying from abroad" needs its own requirement/document path (annex
iii, possibly others not yet surfaced) rather than assuming the
domestic under-16 rules and the adult overseas rules simply compose.
Noted now so it isn't discovered late during that work.

## Open Questions (carried over, still open)

- "Form I.E. 35C"'s exact identity relative to `child_deletion_
  application.pdf`/"Form C" (Conflict 3, UPDATED with `id=24`
  evidence) — that child-name-deletion has its own designated form,
  separate from `id=10`'s general alteration form, is now well
  evidenced (`id=24` lists "Form C" and "Form O" as distinct downloads).
  Whether "Form C" and "Form I.E. 35C" are the SAME document is still
  not established either way — `id=24` never uses the "I.E. 35C" label
  at all.
- The `child_deletion_application.pdf` Rs.250 figure's context — not
  encoded, flagged for re-extraction via Gemini vision (once the daily
  quota this session exhausted resets) or Claude's last-resort stage.
- Appointments, payment method/refunds, pre-expiry renewal timing, and
  a Missions directory — four gaps still genuinely absent from every
  source read. Collection is now only partially closed (see "Downloads
  page" above): a courier-delivery option is confirmed to exist, but
  its fee/eligibility and whether in-person collection supports SMS
  notification or third-party pickup remain open.
- The five OM annexes' trigger facts (which citizenship-proof
  certificate type, PR/settlement status abroad, section-5(2)
  registration) aren't collected by any intake yet — see "Downloads
  page" above. Not a source gap (the documents themselves are read and
  clear); an intake-design gap for a later pass.
