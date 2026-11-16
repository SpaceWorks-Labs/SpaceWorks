"""SECFIX-A F1: who is at the adapter (lead 1, M6 / decision 336j, L-A7).

* a member card's desk QR identifies; at an adapter it needs the member's PIN, and a public card check link never works;
* every member-level failure answers one reason; per-binding and per-space attempt budgets with a doubling cooldown;
* new PINs are 6+ digits and not guessable (old 4-digit PINs keep working);
* a kiosk refusal raised by the workflow is still logged.
"""
import pytest
from django.core.cache import cache
from django.urls import reverse
from rest_framework.exceptions import PermissionDenied

from apps.audit.models import AuditLog
from apps.boxes.models import QrCode
from apps.devices import services_adapter_pin as pin_rules
from apps.devices.models import AdapterAccessLog, AdapterCredential
from apps.devices.services_adapter_core import credential_digest
from apps.makerspaces.models import MakerspaceMembership, MemberCard
from tests.parity_0120.adapter_api.adapter_case import adapter_case, plain_member

pytestmark = pytest.mark.django_db(transaction=True)
PIN = "482913"


@pytest.fixture(autouse=True)
def _fresh_cache():
    cache.clear()
    yield
    cache.clear()


def _door(case, ref="front"):
    made = case["client"].post(reverse("devices:admin-adapter-binding-create", args=[case["device"].pk]), {
        "target_type": "door", "external_ref": ref, "capabilities": ["access.authorize", "door.access"]}, format="json")
    assert made.status_code == 201, made.data
    return made.data["id"]


def _door_case(slug):
    case = adapter_case(slug, caps=("status", "events"), extra=("access.authorize", "door.access"))
    case["door"] = _door(case)
    return case


def _set_pin(case, member, secret=PIN):
    return case["client"].post(reverse("devices:admin-adapter-credentials", args=[case["space"].pk]),
                               {"user_id": member.pk, "kind": "pin", "secret": secret}, format="json")


def _card(space, member, number):
    membership = MakerspaceMembership.objects.get(makerspace=space, user=member)
    card = MemberCard.objects.filter(membership=membership, revoked_at__isnull=True).first()
    if card is None:
        card = MemberCard.objects.create(makerspace=space, membership=membership, card_number=number)
    qr = QrCode.objects.filter(makerspace=space, target_type=QrCode.TargetType.MEMBER_CARD, target_id=card.pk,
                               status=QrCode.Status.ACTIVE).first()
    if qr is None:
        qr = QrCode.objects.create(makerspace=space, target_type=QrCode.TargetType.MEMBER_CARD, target_id=card.pk)
    return card, qr


def _authorize(case, credential, binding=None):
    return case["sim"].post("access/authorize", {"binding_id": binding or case["door"], "credential": credential})


# --- lead 1: a card QR identifies, it does not authenticate ------------------------------------------------------
def test_a_card_qr_alone_opens_nothing_and_asks_for_the_pin():
    case = _door_case("f1-qr-alone")
    member = plain_member("f1-qr-alone-m", case["space"])
    assert _set_pin(case, member).status_code == 201
    _card_row, qr = _card(case["space"], member, 7001)
    response = _authorize(case, {"type": "card_qr", "value": qr.payload})
    assert response.status_code == 200
    assert response.data["allowed"] is False and response.data["reason"] == "pin_required"
    assert AdapterAccessLog.objects.get(binding_id=case["door"]).allowed is False


def test_a_card_qr_with_the_members_pin_opens_the_door():
    case = _door_case("f1-qr-pin")
    member = plain_member("f1-qr-pin-m", case["space"])
    assert _set_pin(case, member).status_code == 201
    _card_row, qr = _card(case["space"], member, 7002)
    response = _authorize(case, {"type": "card_qr", "value": qr.payload, "pin": PIN})
    assert response.data["allowed"] is True and response.data["reason"] == "ok"
    assert AdapterAccessLog.objects.get(binding_id=case["door"]).member_id == member.pk


def test_a_copied_public_check_link_or_token_never_opens_the_door_even_with_the_right_pin():
    from apps.card_designs import tokens
    case = _door_case("f1-qr-link")
    member = plain_member("f1-qr-link-m", case["space"])
    assert _set_pin(case, member).status_code == 201
    card, _qr = _card(case["space"], member, 7003)
    token = tokens.mint("member_card", card).token
    for value in (tokens.url(token), token, f"https://spaces.example/verify/c/{token}/"):
        response = _authorize(case, {"type": "card_qr", "value": value, "pin": PIN})
        assert response.data["allowed"] is False and response.data["reason"] == "unknown_credential", value
    assert not AdapterAccessLog.objects.filter(allowed=True).exists()


def test_a_card_qr_with_a_wrong_pin_or_a_revoked_card_is_refused():
    case = _door_case("f1-qr-wrong")
    member = plain_member("f1-qr-wrong-m", case["space"])
    assert _set_pin(case, member).status_code == 201
    card, qr = _card(case["space"], member, 7004)
    assert _authorize(case, {"type": "card_qr", "value": qr.payload, "pin": "000111"}).data["reason"] == \
        "unknown_credential"
    assert AdapterCredential.objects.get(user=member, kind="pin").failed_attempts == 1
    MemberCard.objects.filter(pk=card.pk).update(revoked_at=card.issued_at)
    assert _authorize(case, {"type": "card_qr", "value": qr.payload, "pin": PIN}).data["reason"] == "unknown_credential"


def test_the_kiosk_refuses_a_card_qr_without_pin_and_opens_a_session_with_it():
    from tests.parity_0120.adapter_api.test_kiosk_checkout import kiosk
    case = kiosk("f1-kiosk-qr")
    assert _set_pin(case, case["member"]).status_code == 201
    _card_row, qr = _card(case["space"], case["member"], 7005)
    url = "kiosk/sessions"
    alone = case["sim"].post(url, {"binding_id": case["kiosk_binding"], "credential": {"type": "card_qr",
                                                                                     "value": qr.payload}})
    assert alone.data["allowed"] is False and "session_id" not in alone.data and alone.data["reason"] == "pin_required"
    paired = case["sim"].post(url, {"binding_id": case["kiosk_binding"], "credential": {
        "type": "card_qr", "value": qr.payload, "pin": PIN}})
    assert paired.status_code == 201 and paired.data["allowed"] is True and paired.data["session_id"]


# --- M6: one denial reason, attempt budgets ---------------------------------------------------------------------
def test_every_member_level_failure_answers_the_same_reason():
    case = _door_case("f1-uniform")
    with_pin = plain_member("f1-uniform-a", case["space"])
    without_pin = plain_member("f1-uniform-b", case["space"])
    assert _set_pin(case, with_pin).status_code == 201
    card_a, _ = _card(case["space"], with_pin, 7101)
    card_b, _ = _card(case["space"], without_pin, 7102)
    AdapterCredential.objects.filter(user=with_pin, kind="pin").update(locked_until=card_a.issued_at.replace(year=2999))
    attempts = [
        {"type": "pin", "value": PIN, "member_number": "999999"},             # unknown member number
        {"type": "pin", "value": PIN, "member_number": str(card_b.card_number)},  # member with no PIN
        {"type": "pin", "value": PIN, "member_number": str(card_a.card_number)},  # locked (right PIN!)
        {"type": "nfc", "value": "DEADBEEF"},                                   # unknown tag
    ]
    assert {_authorize(case, body).data["reason"] for body in attempts} == {"unknown_credential"}
    AdapterCredential.objects.filter(user=with_pin, kind="pin").update(locked_until=None)
    assert _authorize(case, {"type": "pin", "value": PIN, "member_number": str(card_a.card_number)}).data["allowed"]


def test_a_binding_budget_stops_a_keypad_sweep_even_for_the_right_pin_but_not_other_bindings():
    case = _door_case("f1-budget")
    member = plain_member("f1-budget-m", case["space"])
    assert _set_pin(case, member).status_code == 201
    card, _ = _card(case["space"], member, 7201)
    for number in range(9000, 9000 + pin_rules.BUDGETS["binding"]):  # sweep member numbers with a common PIN
        assert _authorize(case, {"type": "pin", "value": "123456", "member_number": str(number)}).data["reason"] == \
            "unknown_credential"
    right = {"type": "pin", "value": PIN, "member_number": str(card.card_number)}
    blocked = _authorize(case, right)
    assert blocked.data["allowed"] is False and blocked.data["reason"] == "too_many_attempts"
    assert AdapterAccessLog.objects.filter(binding_id=case["door"], reason="too_many_attempts").count() == 1
    other = _door(case, ref="back")
    assert _authorize(case, right, binding=other).data["allowed"] is True  # the space budget is not spent
    cache.clear()  # the cooldown ends
    assert _authorize(case, right).data["allowed"] is True


def test_the_space_budget_spans_bindings():
    case = _door_case("f1-space-budget")
    member = plain_member("f1-space-budget-m", case["space"])
    assert _set_pin(case, member).status_code == 201
    card, _ = _card(case["space"], member, 7301)
    doors = [case["door"]] + [_door(case, ref=f"door-{i}") for i in range(4)]
    wrong = 0
    for door in doors:
        for number in range(pin_rules.BUDGETS["binding"] - 1):  # stay under each binding's own budget
            if wrong == pin_rules.BUDGETS["space"]:
                break
            _authorize(case, {"type": "pin", "value": "123456", "member_number": str(8000 + wrong)}, binding=door)
            wrong += 1
    assert wrong == pin_rules.BUDGETS["space"]
    fresh = _door(case, ref="fresh")
    right = {"type": "pin", "value": PIN, "member_number": str(card.card_number)}
    assert _authorize(case, right, binding=fresh).data["reason"] == "too_many_attempts"


def test_nfc_is_not_budgeted_and_the_cooldown_doubles_up_to_a_day():
    case = _door_case("f1-nfc-budget")
    for _ in range(pin_rules.BUDGETS["binding"] + 2):
        assert _authorize(case, {"type": "nfc", "value": "DEADBEEF"}).data["reason"] == "unknown_credential"
    assert not pin_rules.cooling_down(case["space"], None)
    assert [pin_rules.cooldown_for(level) for level in (1, 2, 3, 20)] == [300, 600, 1200, 86400]


def test_the_pin_digest_is_compared_in_constant_time(monkeypatch):
    import hmac
    calls = []
    real = hmac.compare_digest
    monkeypatch.setattr(pin_rules.hmac, "compare_digest", lambda a, b: calls.append(1) or real(a, b))
    case = _door_case("f1-ct")
    member = plain_member("f1-ct-m", case["space"])
    assert _set_pin(case, member).status_code == 201
    card, _ = _card(case["space"], member, 7401)
    assert _authorize(case, {"type": "pin", "value": PIN, "member_number": str(card.card_number)}).data["allowed"]
    assert calls


# --- M6: PIN policy ---------------------------------------------------------------------------------------------
@pytest.mark.parametrize("secret,code", [("4321", "invalid_pin"), ("12345", "invalid_pin"), ("123456", "weak_pin"),
                                         ("111111", "weak_pin"), ("987654", "weak_pin"), ("890123", "weak_pin"),
                                         ("123123", "weak_pin")])
def test_new_pins_must_be_six_digits_and_not_guessable(secret, code):
    case = _door_case(f"f1-policy-{secret}")
    member = plain_member(f"f1-policy-{secret}-m", case["space"])
    refused = _set_pin(case, member, secret)
    assert refused.status_code == 400 and refused.data["code"] == code
    assert not AdapterCredential.objects.filter(user=member).exists()


def test_a_good_new_pin_is_accepted_and_an_old_four_digit_pin_keeps_working():
    case = _door_case("f1-policy-ok")
    member = plain_member("f1-policy-ok-m", case["space"])
    assert _set_pin(case, member, "482913").status_code == 201
    legacy = plain_member("f1-policy-legacy", case["space"])
    AdapterCredential.objects.create(makerspace=case["space"], user=legacy, kind="pin",
                                     digest=credential_digest(case["space"].pk, "pin", "4321", user_id=legacy.pk))
    card, _ = _card(case["space"], legacy, 7501)
    assert _authorize(case, {"type": "pin", "value": "4321", "member_number": str(card.card_number)}).data["allowed"]


# --- L-A7: a kiosk refusal raised by the workflow is still logged ------------------------------------------------
def test_a_kiosk_workflow_refusal_keeps_its_access_log_and_audit_rows(monkeypatch):
    from tests.parity_0120.adapter_api.test_kiosk_checkout import NFC, kiosk

    def refuse(*_args, **_kwargs):
        raise PermissionDenied("Not today.", code="membership_required")

    case = kiosk("f1-kiosk-refused")
    monkeypatch.setattr("apps.hardware_requests.guest_lending.admit_self_checkout", refuse)
    response = case["sim"].post("kiosk/sessions", {"binding_id": case["kiosk_binding"],
                                                   "credential": {"type": "nfc", "value": NFC}})
    assert response.status_code == 403
    row = AdapterAccessLog.objects.get(binding_id=case["kiosk_binding"])
    assert row.allowed is False and row.reason == "membership_required" and row.member_id == case["member"].pk
    assert AuditLog.objects.filter(action="devices.adapter_access_decided", meta__reason="membership_required").exists()
    assert not AuditLog.objects.filter(action="devices.adapter_kiosk_started").exists()


def test_a_kiosk_start_that_is_allowed_is_logged_ok():
    from tests.parity_0120.adapter_api.test_kiosk_checkout import NFC, kiosk
    case = kiosk("f1-kiosk-ok")
    response = case["sim"].post("kiosk/sessions", {"binding_id": case["kiosk_binding"],
                                                   "credential": {"type": "nfc", "value": NFC}})
    assert response.status_code == 201 and response.data["allowed"] is True
    assert AdapterAccessLog.objects.get(binding_id=case["kiosk_binding"]).reason == "ok"
    assert AuditLog.objects.filter(action="devices.adapter_kiosk_started").exists()
