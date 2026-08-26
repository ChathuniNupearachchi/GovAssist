"""Full end-to-end renewal conversations for the QA harness.

Reuses `tests.engine.golden_scenarios.GOLDEN_SCENARIOS` — already
hand-verified `answers` dicts plus expected `expected_labels`/
`expected_fee`/`expected_offices`/`expect_scope_gate` — paired here with
a natural-language OPENING message a citizen would actually type. The
opening message is the only turn that needs the classifier; every
follow-up answer is sent as the literal deterministic-matchable token
(`"30"`, `"true"`, `"Colombo"`, ...) already in the golden scenario's
own `answers` dict, so it hits `app.chat.deterministic`'s matcher
directly — no Gemini call, no ambiguity, and the SAME expected values
this project already verified `resolve_case` against directly
(`tests/engine/test_golden.py`) get verified again here, through the
real conversational API instead of a direct engine call — the gap
identified explicitly: a harness that stops after the opening message
tests the classifier, not the system that would have shipped a Colombo
applicant to Kurunegala.
"""

from __future__ import annotations

from tests.engine.golden_scenarios import GOLDEN_SCENARIOS

_OPENING_MESSAGE_BY_NAME: dict[str, str] = {
    "1. Straightforward adult renewal, Colombo, normal": "my passport expired what do i do",
    "2. Same but urgent": "i need my passport urgently, can you help",
    "3. Name changed after marriage": "i got married and my name changed, need to renew my passport",
    "4. Expired over 5 years ago": "my passport expired like 5 years ago, still valid to renew?",
    "5. Applying from Kandy": "i live in kandy and need to renew my passport",
    "6. Dual citizen": "im a dual citizen and need to renew my sri lankan passport",
    "7. Buddhist priest": "i am a buddhist priest and need to renew my passport",
    "8. No longer holds old passport": "i dont have my old passport anymore, need a new one",
    "9. Applying from abroad": "im currently living abroad and need to renew my passport",
    "10. Name changed and urgent and Kandy": "need an urgent passport renewal, my name changed and im in kandy",
    "11. Under-16 applicant returns the scope gate": "need a passport for my child, she's 10",
    "12. Exactly 16 — fingerprint requirement's lower boundary": "im 16 renewing my passport, do i need fingerprints",
    "13. Exactly 60 — fingerprint requirement's upper boundary, still included": "im 60, renewing my passport, still need fingerprints?",
    "14. Exactly 61 — one past the boundary, fingerprints now excluded": "im 61 renewing my passport",
    "15. Dual citizen under section 19(2) — the AND-condition positive case": "im a dual citizen under the special provisions route, renewing my passport",
    "16. Section 19(2) alone, not a dual citizen — the AND-condition near-miss": "renewing my passport, i applied under the special provisions route",
    "17. Profession stated — the educational certificate branch": "im a doctor renewing my passport",
    "18. Buddhist priest who is also a dual citizen — the set-replacement near-miss": "im a buddhist priest and also a dual citizen, renewing my passport",
    "19. No current passport and a changed name, together": "dont have my old passport and my name changed too, need to renew",
    "20. Everything at once — boundary age, dual citizen, section 19(2), urgent, Kandy": "urgent renewal needed, im a dual citizen under special provisions, in kandy",
    "21. Buddhist monk who is also a teacher — bug #6 regression": "im a buddhist monk who also teaches, renewing my passport",
    "22. Colombo applicant — bug #1 regression (no Kurunegala, no Mission)": "renewing my passport, i live in colombo",
    "23. Under-16 applicant — bug #2 regression (scope gate, not a partial plan)": "need a passport for my 10 year old son",
    "24. Explicit applying_from=sri_lanka — domestic branch (regression)": "renewing my passport, im in kandy",
}

def _conversational_answers(answers: dict[str, str | None]) -> dict[str, str]:
    """The golden `answers` dict is also read directly by `resolve_case`
    in `tests/engine/test_golden.py`, where a `None` value (only
    `district`, only for scenario 9) correctly means "no answer
    recorded" via `.get()`. Here every value is sent as literal chat
    message text instead, and `None` can't be typed — but as of the
    `applying_from` question (Phase 9), scenario 9's `district` is never
    actually asked in the real conversational flow (it's gated on
    `applying_from == "sri_lanka"`, and scenario 9 answers "abroad"), so
    a `None` entry is simply dropped rather than needing a stand-in
    value — `drive_conversation_to_resolution` never looks it up."""
    return {attribute: value for attribute, value in answers.items() if value is not None}


RENEWAL_CONVERSATIONS = [
    {
        **scenario,
        "opening_message": _OPENING_MESSAGE_BY_NAME[scenario["name"]],
        "answers": _conversational_answers(scenario["answers"]),
    }
    for scenario in GOLDEN_SCENARIOS
    if scenario["name"] in _OPENING_MESSAGE_BY_NAME
]

assert len(RENEWAL_CONVERSATIONS) == len(GOLDEN_SCENARIOS), (
    "every golden scenario needs a natural-language opener — see _OPENING_MESSAGE_BY_NAME"
)
