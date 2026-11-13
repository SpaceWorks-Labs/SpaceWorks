"""MOD-1B: requester display labels - every branch, including the PII rules.

Staff surfaces may show a contact email or phone; surfaces for people without loan-contact authority
(`requester_name_label`, `account_name_label`) must never fall back to one. The internal `checkin_<sha256>` hash is
never shown anywhere, even with `allow_internal_fallback`.
"""

from types import SimpleNamespace as NS

import pytest

from apps.hardware_requests.display import (
    account_name_label,
    clean_label,
    is_internal_checkin_username,
    label_from_candidates,
    looks_like_email,
    requester_label,
    requester_name_label,
)

HASH = "checkin_" + "a" * 64


def req(**fields):
    base = dict(requester_name="", requester_contact_email="", requester_username="", requester_contact_phone="", requester=None)
    base.update(fields)
    return NS(**base)


def user(**fields):
    base = dict(display_name="", username="", email="")
    base.update(fields)
    return NS(get_full_name=lambda: base.pop("full", ""), **base)


def test_clean_and_email_helpers():
    assert clean_label(None) == "" and clean_label("  x  ") == "x" and clean_label(0) == ""
    assert looks_like_email("a@b.c") is True and looks_like_email("abc") is False


@pytest.mark.parametrize("value, internal", [
    (HASH, True), (HASH + "@example.com", True), ("checkin_" + "a" * 24, False), ("checkin_" + "a" * 25, True),
    ("checkin_" + "a" * 33, True), ("someone", False), ("", False), ("Checkin_" + "a" * 64, False),
])
def test_the_internal_hash_is_recognised_only_by_prefix_and_length(value, internal):
    assert is_internal_checkin_username(value) is internal


def test_requester_label_prefers_the_captured_name_then_a_real_email_then_phone_then_username():
    assert requester_label(req(requester_name=" Asha ", requester_contact_email="a@b.c")) == "Asha"
    assert requester_label(req(requester_contact_email="a@b.c", requester_username="x")) == "a@b.c"
    assert requester_label(req(requester=NS(email="acct@b.c", username="u"), requester_username="plain")) == "acct@b.c"
    assert requester_label(req(requester_username="login@b.c")) == "login@b.c"
    assert requester_label(req(requester_contact_phone="+15550100", requester_username="plain")) == "+15550100"
    assert requester_label(req(requester_username="plain", requester=NS(username="acct"))) == "plain"
    assert requester_label(req(requester=NS(email="", username="acct"))) == "acct"


def test_requester_label_skips_the_hash_in_every_position_and_falls_back_to_member():
    assert requester_label(req(requester_username=HASH + "@x.test")) == "Member"
    assert requester_label(req(requester_username=HASH)) == "Member"
    assert requester_label(req(requester_username=HASH, requester=NS(email="", username="acct"))) == "acct"
    assert requester_label(req(requester_username=HASH, requester_contact_email=HASH + "@x.test", requester_contact_phone="")) == "Member"
    assert requester_label(req(), fallback="Guest") == "Guest"
    assert requester_label(NS()) == "Member"  # a row with none of the fields at all


def test_the_ledger_flag_never_reveals_the_hash():
    assert requester_label(req(requester_username=HASH), allow_internal_fallback=True) == "Member"
    assert requester_label(req(requester_username=HASH, requester=NS(email="", username="acct")), allow_internal_fallback=True) == "acct"
    assert requester_label(req(requester_name="Asha"), allow_internal_fallback=True) == "Asha"


def test_label_from_candidates_takes_the_first_usable_value():
    assert label_from_candidates(None, "", HASH, "  first ", "second") == "first"
    assert label_from_candidates("", None, HASH) == "Member"
    assert label_from_candidates(HASH, fallback="Walk-in") == "Walk-in"


def test_account_name_label_uses_names_before_a_safe_username_and_never_contact_data():
    assert account_name_label(None) == "Member" and account_name_label(None, fallback="-") == "-"
    assert account_name_label(user(display_name=" Asha ", username="u")) == "Asha"
    assert account_name_label(user(full="Asha Rao", username="u")) == "Asha Rao"
    assert account_name_label(user(username="maker42")) == "maker42"
    for unsafe in ("a@b.c", "+91 98765-43210", "9876543210", HASH, ""):
        assert account_name_label(user(username=unsafe)) == "Member", unsafe
    assert account_name_label(NS(display_name="", username="plain")) == "plain"  # an object without get_full_name


def test_requester_name_label_never_falls_back_to_email_or_phone():
    assert requester_name_label(req(requester_name=" Asha ")) == "Asha"
    assert requester_name_label(req(requester=user(display_name="Account Name"))) == "Account Name"
    assert requester_name_label(req(requester_username="maker42")) == "maker42"
    for unsafe in ("a@b.c", "+15550100", HASH):
        assert requester_name_label(req(requester_username=unsafe, requester_contact_email="x@y.z", requester_contact_phone="+1555")) == "Member", unsafe
    assert requester_name_label(req(), fallback="Borrower") == "Borrower"
