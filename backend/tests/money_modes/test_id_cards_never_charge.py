"""#184 G11 / C-20: ID cards are always free -- no charge path exists for them anywhere.

A static guard, so a later lane that adds a card fee has to break this test and revisit C-20
deliberately rather than slip a charge in.
"""

import re
from pathlib import Path

from apps.payments.availability import SUBJECT_DOMAINS
from apps.payments.models import Payment

APPS = Path(__file__).resolve().parents[2] / "apps"
CARD_SOURCES = (
    *sorted((APPS / "id_programmes").rglob("*.py")),
    *sorted((APPS / "card_designs").rglob("*.py")),
    *sorted((APPS / "events").glob("id_cards*.py")),
)
MONEY_CODE = re.compile(
    r"\b(create_payment|raise_priced|create_checkout(_url)?|charge_tracking_enabled|online_payments_enabled)\b"
    r"|from apps\.payments\b|import apps\.payments\b|\bPayment\.SubjectType\b|\bpricing\.quote\(")


def test_the_card_sources_exist_so_the_guard_is_not_vacuous():
    assert any(path.parts[-2] == "id_programmes" for path in CARD_SOURCES)
    assert any(path.parts[-2] == "card_designs" for path in CARD_SOURCES)
    assert any(path.name == "id_cards.py" for path in CARD_SOURCES)


def test_no_card_module_reaches_the_ledger_or_the_rail():
    offenders = []
    for path in CARD_SOURCES:
        if "migrations" in path.parts:
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            code = line.split("#", 1)[0]
            if MONEY_CODE.search(code):
                offenders.append(f"{path.relative_to(APPS)}:{number}: {line.strip()}")
    assert offenders == [], "ID cards must never charge (C-20):\n" + "\n".join(offenders)


def test_no_payment_subject_or_charge_domain_is_a_card():
    subjects = {value for value, _label in Payment.SubjectType.choices}
    assert not {value for value in subjects if "card" in value or "id_programme" in value}
    assert not {key for key in SUBJECT_DOMAINS if "card" in key}
    assert "cards" not in set(SUBJECT_DOMAINS.values())
