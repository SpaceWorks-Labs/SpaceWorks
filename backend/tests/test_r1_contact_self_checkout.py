"""Owner decision #91: self-checkout without an account where member accounts are off.

Everyone there -- signed in or not -- uses name, phone and an email confirmed by a code.
The evidence rules are unchanged; uploads carry a grant bound to the borrower's email, and
a return must come from the address the checkout used.
"""

import pytest
from django.core.cache import cache
from django.test import override_settings
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.evidence.models import EvidencePhoto
from apps.evidence.storage import EvidenceValidationResult
from apps.hardware_requests.models import HardwareRequest, PublicToolLoan
from apps.makerspaces.models import Makerspace
from tests.test_public_self_checkout import make_product, make_qr

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("_storage", "_fresh")]


@pytest.fixture
def _fresh():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def _storage(monkeypatch):
    monkeypatch.setattr("apps.hardware_requests.self_checkout_contact.presigned_upload",
                        lambda key, content_type: {"url": "http://minio/evidence", "fields": {"key": key}})
    monkeypatch.setattr("apps.evidence.storage.finalize_upload",
                        lambda evidence, max_bytes: EvidenceValidationResult(size=10, content_type="image/png"))


@pytest.fixture
def mailbox(monkeypatch):
    sent = []
    monkeypatch.setattr("apps.integrations.email.send_email_verification_otp",
                        lambda to, code: sent.append((to, code)) or True)
    return sent


def _space(slug, *, member_accounts=False, switch=True):
    space = Makerspace.objects.create(name=slug, slug=slug)
    if not member_accounts:
        space.enabled_modules = [key for key in space.enabled_modules if key not in ("member_accounts", "membership", "mobile")]
        features = set(space.enabled_features or []) | {"inventory.self_checkout"}
        if switch:
            features.add("inventory.contact_self_checkout")
        space.enabled_features = sorted(features)
        space.save(update_fields=["enabled_modules", "enabled_features"])
    return space


def _post(space, path, body, client=None):
    return (client or APIClient(REMOTE_ADDR="10.9.8.7")).post(f"/api/v1/public/{space.slug}/{path}", body, format="json")


def _upload(space, kind, email="ada@example.test"):
    response = _post(space, "tools/evidence-url", {"evidence_type": kind, "content_type": "image/png", "contact_email": email})
    assert response.status_code == 201, response.data
    return response.data["evidence_id"], response.data["evidence_grant"]


def _code(space, mailbox, email="ada@example.test"):
    from datetime import timedelta

    from django.utils import timezone

    from apps.accounts.models import EmailVerificationChallenge

    cache.clear()  # the IP budgets are not what these tests are about
    # A second code for the same address inside the 60-second resend cooldown is a 429.
    EmailVerificationChallenge.objects.update(last_sent_at=timezone.now() - timedelta(minutes=2))
    assert _post(space, "requests/email-code", {"email": email}).status_code == 202
    return mailbox[-1][1]


def _contact(email="ada@example.test", **extra):
    return {"contact_name": "Ada Lovelace", "contact_phone": "+44 20 1234 5678", "contact_email": email, **extra}


@override_settings(API_CLIENT_AUTH_REQUIRED=False)
def test_with_member_accounts_anonymous_self_checkout_is_a_401():
    space = _space("sc-accounts", member_accounts=True)
    response = _post(space, "tools/evidence-url", {"evidence_type": "issue", "content_type": "image/png"})
    assert response.status_code == 401


@override_settings(API_CLIENT_AUTH_REQUIRED=False)
def test_account_less_checkout_and_return_with_a_confirmed_email(mailbox):
    space = _space("sc-contact")
    qr = make_qr(space, make_product(space, public_self_checkout_enabled=True))
    evidence_id, grant = _upload(space, "issue")
    assert EvidencePhoto.objects.get(pk=evidence_id).uploaded_by_id == Makerspace.objects.get(pk=space.pk).anonymous_requester_id

    checkout = _post(space, "tools/checkout", {"payload": qr.payload, "evidence_id": evidence_id, "evidence_grant": grant,
                                               **_contact(email_code=_code(space, mailbox))})

    assert checkout.status_code == 201, checkout.data
    loan = PublicToolLoan.objects.get(makerspace=space)
    request = HardwareRequest.objects.get(pk=loan.request_id)
    assert (request.requester_name, request.requester_contact_email) == ("Ada Lovelace", "ada@example.test")
    assert request.anonymous_idempotency_key_fingerprint and request.anonymous_payload_fingerprint
    assert AuditLog.objects.get(action="public_tool.checked_out").actor is None

    return_id, return_grant = _upload(space, "return")
    returned = _post(space, "tools/return", {"payload": qr.payload, "evidence_id": return_id, "evidence_grant": return_grant,
                                             "remark": "All good", **_contact(email_code=_code(space, mailbox))})
    assert returned.status_code == 200, returned.data
    loan.refresh_from_db()
    assert loan.status == PublicToolLoan.Status.RETURNED


@override_settings(API_CLIENT_AUTH_REQUIRED=False)
def test_a_photo_uploaded_for_another_email_is_refused(mailbox):
    space = _space("sc-grant")
    qr = make_qr(space, make_product(space, public_self_checkout_enabled=True))
    evidence_id, grant = _upload(space, "issue", email="victim@example.test")

    response = _post(space, "tools/checkout", {"payload": qr.payload, "evidence_id": evidence_id, "evidence_grant": grant,
                                               **_contact(email_code=_code(space, mailbox))})

    assert response.status_code == 400 and "evidence_grant" in response.data
    assert not PublicToolLoan.objects.filter(makerspace=space).exists()


@override_settings(API_CLIENT_AUTH_REQUIRED=False)
def test_another_borrower_cannot_return_the_tool(mailbox):
    space = _space("sc-other-returner")
    qr = make_qr(space, make_product(space, public_self_checkout_enabled=True))
    evidence_id, grant = _upload(space, "issue")
    assert _post(space, "tools/checkout", {"payload": qr.payload, "evidence_id": evidence_id, "evidence_grant": grant,
                                           **_contact(email_code=_code(space, mailbox))}).status_code == 201

    other = "mallory@example.test"
    return_id, return_grant = _upload(space, "return", email=other)
    response = _post(space, "tools/return", {"payload": qr.payload, "evidence_id": return_id, "evidence_grant": return_grant,
                                             "remark": "Took it", **_contact(email=other, email_code=_code(space, mailbox, other))})

    assert response.status_code in (400, 403, 409), response.data
    assert PublicToolLoan.objects.get(makerspace=space).status == PublicToolLoan.Status.CHECKED_OUT


@override_settings(API_CLIENT_AUTH_REQUIRED=False)
def test_a_signed_in_caller_also_needs_the_contact_details(mailbox):
    space = _space("sc-signed-in")
    qr = make_qr(space, make_product(space, public_self_checkout_enabled=True))
    client = APIClient(REMOTE_ADDR="10.9.8.6")
    client.force_authenticate(User.objects.create_user(username="sc-staffish", email="s@e.test"))
    evidence_id, grant = _upload(space, "issue")

    response = _post(space, "tools/checkout", {"payload": qr.payload, "evidence_id": evidence_id}, client)

    assert response.status_code == 400 and "contact_email" in response.data


@override_settings(API_CLIENT_AUTH_REQUIRED=False)
def test_account_less_checkout_needs_its_own_switch_but_returns_stay_open(mailbox):
    """#95: the account-less checkout is its own per-space switch, off by default."""
    space = _space("sc-switch-off", switch=False)

    issue = _post(space, "tools/evidence-url", {"evidence_type": "issue", "content_type": "image/png",
                                                "contact_email": "ada@example.test"})
    returning = _post(space, "tools/evidence-url", {"evidence_type": "return", "content_type": "image/png",
                                                    "contact_email": "ada@example.test"})

    assert issue.status_code == 403
    assert returning.status_code == 201, returning.data
    assert AuditLog.objects.filter(action="evidence.upload_url_issued", actor__isnull=True).count() == 1


def test_the_switch_is_registered_off_by_default():
    from apps.makerspaces.capabilities import FEATURE_DEFINITIONS

    definition = next(item for item in FEATURE_DEFINITIONS if item.key == "inventory.contact_self_checkout")
    assert definition.default_enabled is False
    assert definition.requires_features == ("inventory.self_checkout",)


KIT_KEY = "3dfc785b-405a-489a-8a18-de84254ed930"


def _kit_space(slug, **kwargs):
    space = _space(slug, **kwargs)
    space.enabled_features = sorted({*space.enabled_features, "loans.kit_checklist"})
    space.save(update_fields=["enabled_features"])
    product = make_product(space, public_self_checkout_enabled=True,
                           kit_components=[{"key": KIT_KEY, "label": "Driver bits", "quantity": 12}])
    return space, make_qr(space, product)


@override_settings(API_CLIENT_AUTH_REQUIRED=False)
def test_account_less_kit_preview_checks_the_code_without_spending_it(mailbox):
    """#104: the kit contents preview works after the email code, keyed to that email."""
    from apps.accounts.models import EmailVerificationChallenge

    space, qr = _kit_space("sc-kit")
    evidence_id, grant = _upload(space, "issue")
    code = _code(space, mailbox)

    preview = _post(space, "tools/checklist", {"payload": qr.payload, "phase": "issue",
                                               "contact_email": "ada@example.test", "email_code": code})

    assert preview.status_code == 200, preview.data
    assert [row["label"] for row in preview.data["components"]] == ["Driver bits"]
    assert EmailVerificationChallenge.objects.get().consumed_at is None
    checkout = _post(space, "tools/checkout", {"payload": qr.payload, "evidence_id": evidence_id, "evidence_grant": grant,
                                               "kit_checklist": [{"key": KIT_KEY, "present": 12}],
                                               **_contact(email_code=code)})
    assert checkout.status_code == 201, checkout.data

    mine = _post(space, "tools/checklist", {"payload": qr.payload, "phase": "return",
                                            "contact_email": "ada@example.test", "email_code": _code(space, mailbox)})
    other = "mallory@example.test"
    theirs = _post(space, "tools/checklist", {"payload": qr.payload, "phase": "return",
                                              "contact_email": other, "email_code": _code(space, mailbox, other)})
    assert mine.status_code == 200 and mine.data["components"][0]["issue_present"] == 12
    assert theirs.status_code == 404


@override_settings(API_CLIENT_AUTH_REQUIRED=False)
def test_account_less_kit_preview_refuses_a_wrong_code_and_needs_the_switch_to_take(mailbox):
    space, qr = _kit_space("sc-kit-guard")
    _code(space, mailbox)
    wrong = _post(space, "tools/checklist", {"payload": qr.payload, "phase": "issue",
                                             "contact_email": "ada@example.test", "email_code": "000000"
                                             if mailbox[-1][1] != "000000" else "111111"})
    assert wrong.status_code == 400 and "email_code" in wrong.data

    off, off_qr = _kit_space("sc-kit-off", switch=False)
    refused = _post(off, "tools/checklist", {"payload": off_qr.payload, "phase": "issue",
                                             "contact_email": "ada@example.test", "email_code": "123456"})
    assert refused.status_code == 403
