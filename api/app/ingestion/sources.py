"""Single source-to-service configuration — phase-9-service-expansion.

Every URL this project scrapes or fetches (HTML pages, PDFs, and the
photo-studio data endpoint), in one place, each mapped to the service(s)
it supports. Replaces the scattered `TARGET_PAGES`
(`app.scraper.config`) and `TARGET_PDFS` (`app.ingestion.config`) lists
— those two files' current contents are exactly the Phase 1-8 subset of
`SOURCES` below (`service_codes=["passport-renewal", "passport-
amendment"]`, `department="immigration"`). They are not deleted by this
proposal; a follow-up implementation change points the scraper/ingestion
pipeline at this module instead and then retires them, once this
proposal itself is approved.

Adding a new department, or a new source within Immigration, is a
change to `SOURCES` below — not a code change to the scraper, the
ingestion pipeline, or any seed script that reads from it. This is what
makes the source-to-service mapping auditable: `grep service_codes` (or
`sources_for_service("passport-lost-stolen")`) answers "what feeds this
service" without reading scraper code.

See `openspec/changes/phase-9-service-expansion/design.md` for the
research behind every entry — which sources were already ingested vs.
newly fetched, what each one actually says, and the URL discovered only
by reading the page's own markup rather than guessed (the complaint
form's filename has spaces, not underscores; the studio list loads via
an AJAX endpoint the static page never mentions in its visible HTML).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

SourceType = Literal["html", "pdf", "data_endpoint"]

# Every service code this project's SERVICE table names or will name —
# kept here (not imported from app.models) so this module has zero
# runtime dependency on the DB layer; it's pure configuration, read by
# the scraper/ingestion pipeline and by seed scripts, not the other way
# around.
# Seven citizen-intent services (design.md's Round 2 correction: a
# service is what a citizen came in to obtain, not which form
# implements it — first-time application and child-name-deletion are
# their own services despite sharing paperwork with renewal/amendment).
SERVICE_CODES = frozenset(
    {
        "passport-renewal",
        "passport-new",  # first-time applicant — same docs/fee as
        # renewal, different citizen framing (see design.md service #2)
        "passport-lost-stolen",
        "passport-amendment",  # id=10's alteration types EXCEPT child-
        # name-deletion (that's its own service — see design.md's
        # Round 2 correction and Conflict 3)
        "passport-under-16",
        "passport-child-deletion",
        "emergency-certificate",  # India/Nepal only
    }
)
# service_basis="urgent" and applying_from="abroad" are modifiers/
# channels, not services — confirmed against the sources (id=7 states
# urgent plainly as an option within any service; id=7/8/9/10 all list
# Overseas Missions as one of several office options, not a distinct
# thing obtained). Never appear in SERVICE_CODES.


@dataclass(frozen=True)
class Source:
    url: str
    type: SourceType
    department: str
    service_codes: tuple[str, ...]
    # Human-readable note on what this source actually contributes —
    # not a substitute for design.md's full research, a pointer to it.
    note: str
    # Only set for type="data_endpoint": the POST body template and the
    # values to substitute in for each request this source needs to be
    # fully scraped (one request per district, for the studio list).
    endpoint_method: str | None = None
    endpoint_body_template: str | None = None  # "action_type=view&seldisid={value}"
    endpoint_values: tuple[str, ...] = field(default_factory=tuple)


# The site's own district dropdown values (studio_e.php), verbatim —
# NOT this project's own DISTRICTS spelling (app.chat.deterministic).
# Normalization to this project's canonical spelling happens at scrape
# time (see design.md's spelling table), producing AUTHORIZED_STUDIO
# rows keyed by the canonical name, never the site's own id or spelling.
STUDIO_DISTRICT_IDS: dict[str, str] = {
    "1": "Colombo",
    "3": "Gampaha",
    "4": "Kalutara",  # site: "Kaluthara"
    "5": "Galle",
    "6": "Matara",
    "7": "Hambantota",  # site: "Hambanthota"
    "8": "Kandy",
    "9": "Matale",  # site: "Mathale"
    "10": "Nuwara Eliya",
    "11": "Monaragala",
    "12": "Badulla",
    "13": "Kegalle",
    "14": "Ratnapura",  # site: "Rathnapura"
    "15": "Kurunegala",
    "16": "Puttalam",  # site: "Puttlam"
    "17": "Anuradhapura",
    "18": "Polonnaruwa",
    "19": "Trincomalee",
    "20": "Batticaloa",  # site: "Batticalo"
    "21": "Ampara",
    "22": "Vavuniya",
    "23": "Mannar",
    "24": "Kilinochchi",
    "25": "Mullaitivu",  # site: "Mulathiw"
    "26": "Jaffna",
}
# id "2" is genuinely absent from the site's own dropdown — confirmed
# directly from the raw <option> markup, not a scraping gap.

SOURCES: list[Source] = [
    # --- Already ingested (Phase 1-8) ---
    Source(
        url="https://www.immigration.gov.lk/pages_e.php?id=7",
        type="html",
        department="immigration",
        service_codes=(
            "passport-renewal",
            "passport-new",
            "passport-amendment",
            "passport-lost-stolen",
            "emergency-certificate",
        ),
        note="General info: eligibility, office hours, urgent-service modifier, "
        "passport types (incl. Emergency Certificate), fingerprint age range 16-60.",
    ),
    Source(
        url="https://www.immigration.gov.lk/pages_e.php?id=8",
        type="html",
        department="immigration",
        service_codes=(
            "passport-renewal",
            "passport-new",
            "passport-under-16",
            "passport-lost-stolen",
            "emergency-certificate",
        ),
        note="Largest single source: ordinary/diplomatic/official passport docs "
        "(diplomatic/official out of GovAssist's scope — see design.md), NMRP, "
        "Identification Certificate (foreigner-only, out of scope), full "
        "minor/adopted-child section (docs + both 3yr/10yr fee tables), dual "
        "citizen, lost-passport fine.",
    ),
    Source(
        url="https://www.immigration.gov.lk/pages_e.php?id=9",
        type="html",
        department="immigration",
        service_codes=(
            "passport-renewal",
            "passport-new",
            "passport-amendment",
            "passport-child-deletion",
            "passport-lost-stolen",
        ),
        note="The overseas channel — applies across every service when "
        "applying_from=abroad, not a service of its own (unconfirmed for "
        "passport-under-16/emergency-certificate specifically — see design.md). "
        "Also duplicates id=11's support-services content verbatim "
        "(certification/translation fees).",
    ),
    Source(
        url="https://www.immigration.gov.lk/pages_e.php?id=10",
        type="html",
        department="immigration",
        service_codes=("passport-amendment", "passport-child-deletion"),
        note="7 alteration types at a flat LKR 1,200 — only Change of Name is "
        "currently seeded (confirmed directly against REQUIREMENT rows). "
        "Includes 'Deletion of a child's name', which is its own service "
        "(passport-child-deletion, not an passport-amendment row) — see "
        "design.md's Round 2 correction and Conflict 3.",
    ),
    Source(
        url="https://www.immigration.gov.lk/studio_e.php",
        type="html",
        department="immigration",
        service_codes=(
            "passport-renewal",
            "passport-new",
            "passport-amendment",
            "passport-child-deletion",
            "passport-lost-stolen",
            "passport-under-16",
        ),
        note="Static shell only — the district dropdown and an empty results "
        "table. The actual data is the data_endpoint source below.",
    ),
    Source(
        url="https://www.immigration.gov.lk/content/files/applications/instructions_english_td.pdf",
        type="pdf",
        department="immigration",
        service_codes=(
            "passport-under-16",
            "passport-child-deletion",
            "passport-lost-stolen",
            "passport-renewal",
            "passport-new",
            "emergency-certificate",
        ),
        note="Scanned, no text layer — extracted via the Claude-vision last-resort "
        "stage. Section (c) is the under-16 document/consent requirements "
        "(incl. (c)(viii) child-name-deletion, Rs.1,200, 'Form I.E. 35C'); "
        "section (e)/(f) is the lost-passport fine and fee tables, incl. the "
        "Emergency Certificate India/Nepal fee.",
    ),
    Source(
        url="https://www.immigration.gov.lk/content/files/applications/passport_application.pdf",
        type="pdf",
        department="immigration",
        service_codes=("passport-renewal", "passport-new", "passport-under-16", "emergency-certificate"),
        note="Form K-35A — same form for renewal, first-time, minor, and "
        "Emergency Certificate applications (different tick-box selection).",
    ),
    Source(
        url="https://www.immigration.gov.lk/content/files/applications/amendment.pdf",
        type="pdf",
        department="immigration",
        # passport-child-deletion REMOVED as of the Downloads-page
        # re-verification (pages_e.php?id=24, "Form O") — this is the
        # general alteration form for Amendments & Alterations
        # specifically, no longer recommended for child-name-deletion
        # (that's Form C / child_deletion_application.pdf instead). See
        # design.md's Conflict 3 update.
        service_codes=("passport-amendment",),
        note="The general alteration application form ('Form O' per id=24) — "
        "no longer used for child-name-deletion, which has its own designated "
        "form ('Form C', child_deletion_application.pdf) per id=24's new "
        "evidence. See design.md's Conflict 3 update.",
    ),
    # --- Ingested this session (service #3 implementation) — was
    # "fetched, read, not yet ingested" during the original research
    # pass; see app.ingestion.phase9_lost_stolen.
    Source(
        url="https://www.immigration.gov.lk/pages_e.php?id=12",
        type="html",
        department="immigration",
        service_codes=("passport-lost-stolen",),
        note="Reporting/cancellation process only (domestic hotline+police, "
        "overseas police-report+complaint-form) — no fee or replacement-document "
        "info; that's on id=8. Its own numbered steps list the hotline call AND "
        "the police complaint sequentially (steps 1 and 2), not as alternatives — "
        "RESOLVES Conflict 1 (previously 'unresolved') in favor of both being "
        "required. See design.md's Conflict 1 update.",
    ),
    Source(
        # NB: the site's own filename has spaces, URL-encoded as %20 — a
        # literal underscore-only guess (complaint_form_stolen_and_lost_
        # sri_lankan_passport.pdf) 404s. Found by reading id=12's actual
        # <a href> markup, not guessed.
        url="https://www.immigration.gov.lk/content/files/applications/"
        "complaint_form%20_stolen_and_lost_sri%20lankan_passport.pdf",
        type="pdf",
        department="immigration",
        service_codes=("passport-lost-stolen",),
        note="Overseas-path complaint form — has a text layer, extracted cleanly "
        "(no OCR needed). Applicant/contact/passport-loss fields. CONFIRMED "
        "word-for-word identical in extracted text to om/annex_iv.pdf (the "
        "Downloads-page work had left this as 'not confirmed identical, related "
        "fact' — now compared directly, both ingested: same document, "
        "republished under two filenames/paths) — its own text: 'This form to "
        "be used by Sri Lankans abroad in case of stolen or lost passport,' "
        "confirming no separate Department complaint FORM exists for the "
        "domestic path (the police's own report is what's produced there).",
    ),
    Source(
        url="https://www.immigration.gov.lk/content/files/applications/child_deletion_application.pdf",
        type="pdf",
        department="immigration",
        service_codes=("passport-child-deletion", "passport-under-16"),
        note="Scanned, no text layer. Tesseract-OCR'd (Gemini vision unavailable "
        "this pass — daily free-tier quota exhausted). English portions legible "
        "(confirms 'APPLICATION FOR DELETION OF CHILDREN', photo/attestation "
        "requirements); Sinhala portions garbled. Rs.250 figure present but its "
        "context is not legible with confidence — NOT to be encoded as a "
        "FEE_RULE until re-extracted. id=24 labels this file's download link "
        "'Form C' for 'Children Deletion', a separate line item from 'Form O' "
        "(amendment.pdf) — strong new evidence child-name-deletion has its own "
        "designated form. Whether 'Form C' and instructions_english_td.pdf's "
        "'Form I.E. 35C' are the same document is still not established either "
        "way — id=24 never uses the 'I.E. 35C' label. See design.md's Conflict "
        "3 update and Open Questions.",
    ),
    # --- Ingested this session: the Downloads page (pages_e.php?id=24) ---
    # and every PDF it links that this project didn't already have —
    # see design.md's "Downloads page" section for the full read-through
    # (which resolved Conflict 3 further, the collection gap, and a
    # second domestic form) and `app.ingestion.phase9_downloads` for the
    # ingestion script.
    Source(
        url="https://www.immigration.gov.lk/pages_e.php?id=24",
        type="html",
        department="immigration",
        service_codes=(
            "passport-renewal", "passport-new", "passport-amendment",
            "passport-child-deletion", "passport-lost-stolen",
            "passport-under-16", "emergency-certificate",
        ),
        note="The Downloads/Applications index — every form's exact download "
        "link and label in one place. Confirms 'Form O' (Amendments & "
        "Alterations, amendment.pdf) and 'Form C' (Children Deletion, "
        "child_deletion_application.pdf) as separate line items (Conflict 3 "
        "new evidence); states downloaded forms must be laser-printed on A4 "
        "paper; distinguishes two domestic K-35A variants ('Online Fill and "
        "Printable' vs. 'Downloadable'); lists the Overseas Missions form set.",
    ),
    Source(
        url="https://www.immigration.gov.lk/content/files/applications/application.pdf",
        type="pdf",
        department="immigration",
        service_codes=("passport-renewal", "passport-new", "passport-under-16", "emergency-certificate"),
        note="Form K-35A, second domestic variant — id=24's 'Downloadable Format' "
        "column (vs. passport_application.pdf's 'Online Fill and Printable'). "
        "Same fields as passport_application.pdf (NIC, DOB, birth certificate, "
        "profession, dual-citizenship Y/N, declaration) — offered alongside it, "
        "not in place of it, so a citizen without a computer to fill the online "
        "variant still has a usable path (see app.seed.phase4_renewal).",
    ),
    Source(
        url="https://www.immigration.gov.lk/content/files/applications/new_om_application_form.pdf",
        type="pdf",
        department="immigration",
        # Its own extracted text covers a child under 16 (fields 18+: "If "
        # this application is for a child below the age of 16 years...")
        # and Emergency/Identity Certificate (form header: "APPLICATION "
        # FOR A SRI LANKAN PASSPORT, EMERGENCY/IDENTITY CERTIFICATE") on
        # the SAME form — passport-under-16/emergency-certificate mapped
        # here for when those services are built, not yet encoded as
        # Requirements (see design.md's "Overseas Missions form set" and
        # "Flag for later" notes).
        service_codes=("passport-renewal", "passport-new", "passport-under-16", "emergency-certificate"),
        note="Form K-35A, Overseas Missions variant — id=24: 'Overseas Missions "
        "Passport Application (Only for overseas applicants)'. A DIFFERENT PDF "
        "from the domestic K-35A variants, gated on applying_from == \"abroad\" "
        "in app.seed.phase4_renewal. Mixed-quality extraction (embedded fonts "
        "without a ToUnicode CMap for the Sinhala/Tamil portions produce "
        "unmapped-glyph artifacts; the English portions read cleanly).",
    ),
    Source(
        url="https://www.immigration.gov.lk/content/files/om/annex_i.pdf",
        type="pdf",
        department="immigration",
        # Tentative — the intake doesn't yet collect which route an
        # overseas applicant's citizenship came from, so this isn't
        # encoded as a Requirement for any service yet. See design.md.
        service_codes=("passport-renewal", "passport-new"),
        note="'Certificate to prove Sri Lankan Citizenship' — NOT a form to "
        "fill; a checklist of which existing certificate qualifies (Dual "
        "Citizenship Certificate, Overseas Birth Registration Certificate, "
        "citizenship registration under Citizenship Act sections 8/11/12/13, "
        "or a citizenship grant to an Indian- or Chinese-origin person). "
        "Trigger (read from the document's own content, not its title): "
        "needed by an overseas applicant whose citizenship was acquired by "
        "one of these routes rather than by birth with an ordinary existing "
        "Sri Lankan passport. Genuinely short (386 chars extracted) — it's a "
        "one-paragraph list, not a multi-page form.",
    ),
    Source(
        url="https://www.immigration.gov.lk/content/files/om/annex_ii.pdf",
        type="pdf",
        department="immigration",
        service_codes=("passport-renewal", "passport-new"),
        note="'Affidavit not obtain citizenship' — an affidavit for an overseas "
        "applicant who holds Indefinite Leave to Remain/Settlement/Permanent "
        "Residence/Indefinite Leave to Enter in their country of residence, "
        "declaring they remain solely a Sri Lankan citizen and have not "
        "obtained that country's (or any other's) citizenship, asylum, or "
        "refugee status. Trigger (from the affidavit's own text): applies "
        "specifically to an overseas applicant with PR/settlement status "
        "abroad — distinct from annex_v below, which is about a specific "
        "citizenship-registration route, not residency status.",
    ),
    Source(
        url="https://www.immigration.gov.lk/content/files/om/annex_iii.pdf",
        type="pdf",
        department="immigration",
        service_codes=("passport-under-16",),
        note="'Parent's Consent Letter' — CONFIRMED identical in content to "
        "request_letter.pdf below (same trilingual 'Request to issue a "
        "separate passport to child' text; same char count once extracted, "
        "different underlying PDF bytes — republished under two URLs/labels). "
        "Trigger: a parent/guardian consenting to their child receiving a "
        "SEPARATE passport rather than being endorsed on a parent's passport. "
        "Confirms an overseas Mission accepts a minor's application at all — "
        "see design.md's 'Flag for later' note on a possible distinct "
        "minor-and-overseas path.",
    ),
    Source(
        url="https://www.immigration.gov.lk/content/files/om/annex_iv.pdf",
        type="pdf",
        department="immigration",
        service_codes=("passport-lost-stolen",),
        note="'Lost or Stolen passport complaint form' (overseas). Its own text: "
        "\"This form to be used by Sri Lankans abroad in case of stolen or "
        "lost passport\" — submit with a local Police Report to the nearest "
        "Sri Lankan Diplomatic Mission; accepting the complaint immediately "
        "cancels the passport worldwide. CONFIRMED word-for-word identical in "
        "extracted text to complaint_form%20_stolen_and_lost_sri%20lankan_"
        "passport.pdf above (service #3 implementation session: both ingested, "
        "compared directly) — different bytes/filename, same document, "
        "republished under two paths (this one under om/). Used as the "
        "overseas reporting Requirement's citation in "
        "app.seed.phase9_lost_stolen; the domestic-path URL above is the one "
        "kept as the canonical citation elsewhere for stability.",
    ),
    Source(
        url="https://www.immigration.gov.lk/content/files/om/annex_v.pdf",
        type="pdf",
        department="immigration",
        service_codes=("passport-renewal", "passport-new"),
        note="'Affidavit for Citizenship Declaration' — its own text: \"AFFIDAVIT "
        "FOR CITIZENSHIP DECLARATION UNDER SECTION 5(2) OF THE CITIZENSHIP "
        "ACT\", for an applicant whose birth was registered under section 5(2) "
        "of the Ceylon Citizenship Act (citizenship by descent, born abroad to "
        "a Sri Lankan parent), declaring they wish to retain Sri Lankan "
        "citizenship and haven't obtained any other. Trigger: specifically a "
        "section-5(2)-registered citizen — a narrower, different fact from "
        "annex_ii's PR/settlement-status trigger, and from section_19_2 "
        "(already asked in this intake — a different section of the same "
        "Act, about the special-provisions dual-citizenship route).",
    ),
    Source(
        url="https://www.immigration.gov.lk/content/files/applications/CourierSriLankanPassports.pdf",
        type="pdf",
        department="immigration",
        service_codes=(
            "passport-renewal", "passport-new", "passport-amendment",
            "passport-child-deletion", "passport-lost-stolen",
            "passport-under-16", "emergency-certificate",
        ),
        note="'Application to Courier Sri Lankan Passports' — partially answers "
        "the general-info Collection gap: a courier-delivery option exists as "
        "a separate application (name/passport number, reason to courier, "
        "name of courier service, relevant foreign Mission/consulate, "
        "destination). Extraction quality issue: pdfplumber returned every "
        "line character-reversed (a PDF encoding artifact, not a scanned-PDF "
        "OCR issue) — readable by a human reversing each line, but NOT clean "
        "citation-quality text; not re-extracted via the OCR chain this pass. "
        "Fee/eligibility for courier collection not legible in what was "
        "extracted — still a partial gap, not fully closed. See design.md's "
        "Collection gap update.",
    ),
    Source(
        url="https://www.immigration.gov.lk/content/files/applications/request_letter.pdf",
        type="pdf",
        department="immigration",
        service_codes=("passport-under-16",),
        note="'Request to issue a separate passport to child' — CONFIRMED "
        "identical in content to om/annex_iii.pdf above (see that entry). A "
        "parent/guardian consent letter for a child receiving their own "
        "separate passport rather than being endorsed on a parent's passport.",
    ),
    Source(
        url="https://www.immigration.gov.lk/json/function.php",
        type="data_endpoint",
        department="immigration",
        service_codes=(
            "passport-renewal",
            "passport-new",
            "passport-amendment",
            "passport-child-deletion",
            "passport-lost-stolen",
            "passport-under-16",
            "emergency-certificate",
        ),
        note="Authorized photo studios by district — a lookup table, not RAG "
        "content (302 rows for Colombo alone). One POST per district id; see "
        "STUDIO_DISTRICT_IDS for the site's own id->name mapping and the "
        "normalization to this project's canonical district spelling.",
        endpoint_method="POST",
        endpoint_body_template="action_type=view&seldisid={value}",
        endpoint_values=tuple(STUDIO_DISTRICT_IDS.keys()),
    ),
    # --- Read, but explicitly NOT proposed for ingestion ---
    # pages_e.php?id=11 (Passport Support Services): certification/
    # translation fees, duplicated verbatim inside id=9 — see id=9's note
    # above. Deliberately omitted from SOURCES, not forgotten; see
    # design.md's "already read, redundant" note.
]


def sources_for_service(service_code: str) -> list[Source]:
    """Every source that supports a given service, in `SOURCES` order —
    the audit query this module exists to make possible without reading
    scraper code."""
    return [s for s in SOURCES if service_code in s.service_codes]


def sources_by_department(department: str) -> list[Source]:
    return [s for s in SOURCES if s.department == department]
