"""Golden open-question scenarios — langgraph-orchestration-branch Task
Group 3 (answer-quality-evaluation spec). Ten hand-verified scenarios
run through the real agent, deliberately chosen to discriminate rather
than to pass: hard paraphrases far from source wording, multi-tool
questions, exact-identifier queries, near-miss out-of-corpus queries
adjacent to real topics, and cases expected to be refused.

Every expected fact below was verified directly against the actual
DOCUMENT_CHUNK rows for pages_e.php?id=8/9/10 (not guessed) — see the
inline citation note on each scenario.

`reference` (hand-written, concise) is set on the 7 scenarios that
expect a grounded answer with definite, checkable content — RAGAS's
context precision and context recall (Task Group 4) need a reference
answer to score against; it's absent on scenarios 8-10, which are about
refusal/ambiguity, not generation quality, so they aren't part of the
RAGAS dataset (see `ragas_baseline.py`).
"""

SCENARIOS = [
    {
        "name": "1. Lost-passport-abroad, phrased far from source wording",
        "query": (
            "My passport got stolen while I was traveling in another "
            "country — what do I need to sort out before I can travel "
            "back to Sri Lanka?"
        ),
        # Source (id=8, "documents required for a lost passport"): a
        # police complaint including the lost passport number, and — if
        # lost abroad — "the temporary travel document (NMRP) used to
        # arrive in Sri Lanka". Neither "stolen" nor "travel back" nor
        # "sort out" appear in the source at all — a genuine paraphrase.
        "expect_grounded": True,
        "must_contain_any": ["police", "NMRP", "temporary travel document"],
        "reference": (
            "File a police complaint including the lost passport number "
            "(obtainable from the Colombo Head Office or a Regional Office "
            "if unknown). Since the passport was lost abroad, apply at the "
            "nearest Sri Lankan Overseas Mission for an NMRP or Temporary "
            "Travel Document, valid only for one-way travel to Sri Lanka. "
            "Keep the NMRP/travel document with a photocopy — it must be "
            "submitted, along with the police complaint, when applying for "
            "the replacement passport back in Sri Lanka."
        ),
    },
    {
        "name": "2. Exact identifier — NMRP",
        "query": "What is an NMRP?",
        # Same source passage as #1 — defines NMRP as the temporary
        # travel document used to arrive in Sri Lanka after a passport
        # is lost abroad.
        "expect_grounded": True,
        "must_contain_any": ["temporary travel document", "lost"],
        "reference": (
            "NMRP stands for Non-Machine Readable Passport, a temporary "
            "travel document (along with the similar Temporary Travel "
            "Document) issued to Sri Lankans whose passports have been "
            "lost, stolen, or expired while in a foreign country. It is "
            "obtained from Overseas Sri Lankan Missions and is valid only "
            "for one-way travel back to Sri Lanka."
        ),
    },
    {
        "name": "3. Exact identifier — a circular number",
        "query": "What is circular DIE/OM/CIR/2017/01 about?",
        # id=9 ("Overseas Applications"): "Relevant Circular for finger
        # prints : DIE/OM/CIR/2017/01" — an exact identifier that only
        # ever appears in this one passage.
        "expect_grounded": True,
        "must_contain_any": ["fingerprint", "finger print"],
        "reference": (
            "Circular DIE/OM/CIR/2017/01 is the relevant circular for "
            "fingerprints for overseas passport applications, submitted "
            "through a Sri Lankan Diplomatic Mission."
        ),
    },
    {
        "name": "4. Age-tiered fee — a real system gap risk, not a guess",
        "query": "How much does an urgent passport renewal cost for a 10-year-old?",
        # id=8 has TWO separate fee tables — the adult one (Normal
        # 10,000 / Urgent 20,000) and a distinct "below 16 years of age"
        # one (Normal 3,000 / Urgent 9,000). The correct answer here is
        # LKR 9,000. The agent's get_fee tool takes only (service,
        # urgency) — no age parameter — so a naive call returns the
        # ADULT fee (20,000), which would still pass this project's
        # tool-result verification (a real tool did return 20,000) while
        # being the wrong number for a 10-year-old. This scenario is
        # deliberately included to surface that gap if it's real, not to
        # assert the system already handles it — see the test's handling
        # of this scenario specifically.
        "expect_grounded": True,
        "must_contain_any": ["9,000", "9000"],
        "known_risk": "get_fee has no age parameter; may state the adult fee (20,000) instead",
        "reference": "The urgent renewal fee for an applicant under 16 years of age is LKR 9,000.",
    },
    {
        "name": "5. Alteration fee — exact amount, paraphrased",
        "query": "How much does it cost to add my profession to my passport?",
        # id=10's alteration table: "Profession inclusion" — LKR 1,200.
        # The query never says "alteration" or "inclusion".
        "expect_grounded": True,
        "must_contain_any": ["1,200", "1200"],
        "reference": "Adding or updating a profession on a passport (a 'Profession inclusion' alteration) costs LKR 1,200.",
    },
    {
        "name": "6. Multi-tool comparison — both fees required",
        "query": "Should I amend my passport or apply for a new one, and how much will each cost?",
        "expect_grounded": True,
        "must_contain_any": ["10,000", "10000"],
        "must_also_contain_any": ["1,200", "1200"],
        "min_tool_calls": 2,
        "reference": (
            "An amendment (alteration) to an existing valid passport costs LKR 1,200 at "
            "normal service and only changes data already in the passport. A full renewal "
            "costs LKR 10,000 at normal service and issues a new passport — needed when the "
            "existing passport itself must be replaced (expired, damaged, or full)."
        ),
    },
    {
        "name": "7. Multi-tool — fee, office, and the urgent conflict note",
        "query": "I need an urgent passport and I live in Kandy — what will it cost, and which office do I go to?",
        "expect_grounded": True,
        "must_contain_any": ["20,000", "20000"],
        "must_also_contain_any": ["Head Office"],
        "min_tool_calls": 2,
        "reference": (
            "An urgent passport renewal costs LKR 20,000. Applications should go to the "
            "Head Office in Battaramulla — the Department's guidance on urgent service at "
            "Regional Offices such as Kandy's is internally inconsistent, so confirm "
            "directly with the office before traveling for urgent service outside the "
            "Head Office."
        ),
    },
    {
        "name": "8. Near-miss out-of-corpus — driving license, adjacent to a real office",
        "query": "Can I renew my driving license at the passport office in Kandy?",
        # Driving licenses are Motor Traffic's domain (out of Phase 1's
        # scope entirely, per CLAUDE.md) — genuinely absent from this
        # corpus, but the query names a real in-corpus office (Kandy),
        # making the refusal harder than a purely off-topic query.
        "expect_grounded": False,
    },
    {
        "name": "9. Near-miss out-of-corpus — adjacent to a real topic (dual citizenship)",
        "query": (
            "What are the passport rules for a Sri Lankan citizen who "
            "also holds Indian citizenship, applying from India?"
        ),
        # Dual citizenship generically is in-corpus (id=8); India-
        # specific or overseas-mission-specific processing for it is
        # not — ambiguous enough that this is reported, not asserted,
        # since a careful hedge citing the generic dual-citizenship
        # passage could be defensible and a fabricated India-specific
        # answer would not be.
        "expect_grounded": None,  # reported, not asserted
    },
    {
        "name": "10. Explicit out-of-scope refusal — online submission",
        "query": "How do I log into the online passport application portal?",
        # CLAUDE.md: "Online submission or payment" is explicitly out of
        # scope for this build. No such portal exists in the corpus.
        "expect_grounded": False,
    },
]
