"""Owner decision #80 (revising #75f): who may request depends on member accounts.

A space WITH member accounts requires a signed-in account. A space WITHOUT them has accounts
for staff only, so a public borrower asks with name, phone and email, and proves the email
with a one-time code before the request exists. Phone and email are encrypted, staff-only;
the typed name is the public name.
"""

import pytest
from django.core.cache import cache
from django.db import connection
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import EmailVerificationChallenge, User
from apps.audit.models import AuditLog
from apps.hardware_requests.models import HardwareRequest
from apps.hardware_requests.serializers import PublicRequestStatusSerializer
from apps.inventory.models import InventoryProduct
from apps.inventory.public_stats_hardware import public_display_name
from apps.makerspaces.models import Makerspace
from apps.makerspaces.module_profiles import RECOMMENDED, profile_modules
from tests.historic_anonymous import historic_anonymous_request
from tests.return_helpers import authenticated_client, make_member

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _fresh_throttles():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def mailbox(monkeypatch):
    sent = []
    monkeypatch.setattr("apps.integrations.email.send_email_verification_otp",
                        lambda to, code: sent.append((to, code)) or True)
    return sent


def _space(slug, *, member_accounts):
    modules = [key for key in profile_modules(RECOMMENDED)
               if member_accounts or key not in ("member_accounts", "mobile", "membership")]
    if member_accounts and "member_accounts" not in modules:
        modules.append("member_accounts")
    return Makerspace.objects.create(
        name=slug, slug=slug, enabled_modules=modules,
        enabled_features=["loans.enabled", "inventory.self_checkout"],
    )


def _product(space):
    return InventoryProduct.objects.create(
        makerspace=space, name="Logic analyzer", total_quantity=10, available_quantity=10, is_public=True,
    )


def _payload(product, **extra):
    return {"contact_name": "Ada Lovelace", "contact_email": "Ada@Example.test",
            "contact_phone": "+44 20 1234 5678", "requested_for": "Bench diagnostics",
            "items": [{"product_id": product.pk, "quantity": 1}], **extra}


def _submit(space, payload, client=None):
    return (client or APIClient()).post(
        reverse("hardware_requests:request-submit", args=[space.slug]), payload, format="json",
    )


def _send_code(space, email="ada@example.test", client=None):
    return (client or APIClient()).post(
        reverse("hardware_requests:request-contact-code", args=[space.slug]), {"email": email}, format="json",
    )


# --- a space WITH member accounts ---------------------------------------------------------


def test_with_member_accounts_an_anonymous_submission_is_a_401_and_creates_nothing():
    space = _space("acct-required", member_accounts=True)

    response = _submit(space, _payload(_product(space), email_code="123456"))

    assert response.status_code == 401
    assert not HardwareRequest.objects.filter(makerspace=space).exists()
    space.refresh_from_db()
    assert space.anonymous_requester_id is None


def test_with_member_accounts_the_email_code_route_is_a_404():
    assert _send_code(_space("acct-no-code", member_accounts=True)).status_code == 404


def test_signed_in_submit_ignores_contact_spoofing_and_keeps_account_identity():
    space = _space("acct-spoof", member_accounts=True)
    user = User.objects.create_user(username="real-account", display_name="Real Account",
                                    email="REAL@EXAMPLE.TEST", phone="trusted")
    client = APIClient()
    client.force_authenticate(user)
    payload = _payload(_product(space), contact_name="x" * 201, contact_email="not-an-email")

    response = _submit(space, payload, client)

    assert response.status_code == 201, response.data
    row = HardwareRequest.objects.get(makerspace=space)
    assert row.requester == user
    assert (row.requester_name, row.requester_contact_email) == (user.display_name, user.email)
    assert row.anonymous_idempotency_key_fingerprint == ""
    assert AuditLog.objects.get(action="request.submitted").actor == user


# --- a space WITHOUT member accounts ------------------------------------------------------


def test_without_member_accounts_bootstrap_advertises_the_contact_path():
    space = _space("contact-bootstrap", member_accounts=False)
    response = APIClient().get(f"/api/v1/bootstrap?slug={space.slug}")
    assert response.status_code == 200
    assert response.data["makerspace"]["request_access"] == "contact"


def test_email_code_is_stored_as_a_fingerprint_audited_and_mailed(mailbox):
    space = _space("contact-code", member_accounts=False)

    response = _send_code(space)

    assert response.status_code == 202
    assert mailbox and mailbox[0][0] == "ada@example.test" and len(mailbox[0][1]) == 6
    challenge = EmailVerificationChallenge.objects.get()
    space.refresh_from_db()
    assert challenge.user_id == space.anonymous_requester_id
    assert "@" not in challenge.email and challenge.code_digest != mailbox[0][1]
    entry = AuditLog.objects.get(action="request.contact_code_sent")
    assert entry.actor is None and entry.meta["email_sent"] is True and "ada" not in str(entry.meta)


def test_a_second_code_inside_the_cooldown_is_throttled(mailbox):
    space = _space("contact-cooldown", member_accounts=False)
    assert _send_code(space).status_code == 202
    assert _send_code(space).status_code == 429
    assert len(mailbox) == 1


@pytest.mark.parametrize("missing", ["contact_name", "contact_phone", "contact_email", "email_code"])
def test_all_contact_fields_and_the_code_are_required(missing, mailbox):
    space = _space(f"contact-missing-{missing.replace('_', '-')}", member_accounts=False)
    _send_code(space)
    payload = _payload(_product(space), email_code=mailbox[0][1])
    payload.pop(missing)

    response = _submit(space, payload)

    assert response.status_code == 400
    assert missing in response.data
    assert not HardwareRequest.objects.filter(makerspace=space).exists()


def test_a_wrong_code_is_refused_burns_an_attempt_and_is_audited(mailbox):
    space = _space("contact-wrong", member_accounts=False)
    _send_code(space)
    wrong = "000000" if mailbox[0][1] != "000000" else "111111"

    response = _submit(space, _payload(_product(space), email_code=wrong))

    assert response.status_code == 400 and "email_code" in response.data
    assert EmailVerificationChallenge.objects.get().failed_attempts == 1
    assert AuditLog.objects.filter(action="request.contact_code_failed").exists()
    assert not HardwareRequest.objects.filter(makerspace=space).exists()


def test_a_code_for_another_address_is_refused(mailbox):
    space = _space("contact-other-address", member_accounts=False)
    _send_code(space, email="victim@example.test")

    response = _submit(space, _payload(_product(space), email_code=mailbox[0][1]))

    assert response.status_code == 400
    assert not HardwareRequest.objects.filter(makerspace=space).exists()


def test_the_right_code_files_a_verified_account_less_request_once(mailbox):
    space = _space("contact-ok", member_accounts=False)
    product = _product(space)
    _send_code(space)
    payload = _payload(product, email_code=mailbox[0][1])

    response = _submit(space, payload)

    assert response.status_code == 201, response.data
    space.refresh_from_db()
    row = HardwareRequest.objects.get(makerspace=space)
    assert row.requester_id == space.anonymous_requester_id
    assert (row.requester_name, row.requester_contact_email, row.requester_contact_phone) == (
        "Ada Lovelace", "ada@example.test", "+44 20 1234 5678",
    )
    assert row.requester_contact_verified is True and row.anonymous_idempotency_key_fingerprint
    entry = AuditLog.objects.get(action="request.submitted")
    assert entry.actor is None and entry.meta["account_less"] is True
    assert _submit(space, payload).status_code == 400  # the code is single-use


def test_a_signed_in_caller_also_uses_the_contact_path_without_member_accounts(mailbox):
    """#91: without member accounts EVERYONE uses the contact form, staff sign-ins included."""
    space = _space("contact-signed-in", member_accounts=False)
    user = User.objects.create_user(username="oidc-person", display_name="Oidc Person", email="o@e.test")
    client = APIClient()
    client.force_authenticate(user)
    product = _product(space)

    bare = _submit(space, {"requested_for": "x", "items": [{"product_id": product.pk, "quantity": 1}]}, client)
    _send_code(space, client=client)
    confirmed = _submit(space, _payload(product, email_code=mailbox[0][1]), client)

    assert bare.status_code == 400 and "contact_email" in bare.data
    assert confirmed.status_code == 201, confirmed.data
    space.refresh_from_db()
    assert HardwareRequest.objects.get(makerspace=space).requester_id == space.anonymous_requester_id


def test_contact_details_are_encrypted_at_rest_and_never_public(mailbox):
    from tests.encryption.conftest import enabled_encryption

    space = _space("contact-encrypted", member_accounts=False)
    with enabled_encryption():
        _send_code(space)
        assert _submit(space, _payload(_product(space), email_code=mailbox[0][1])).status_code == 201
        row = HardwareRequest.objects.get(makerspace=space)
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT requester_contact_email, requester_contact_phone FROM hardware_requests_hardwarerequest "
                "WHERE id = %s", [row.pk],
            )
            raw_email, raw_phone = cursor.fetchone()
        assert raw_email.startswith("pii:gcm:v1:") and raw_phone.startswith("pii:gcm:v1:")
        public = PublicRequestStatusSerializer(row).data
    assert "ada@example.test" not in str(public) and "1234" not in str(public)


def test_the_typed_name_is_the_public_borrower_name():
    space = _space("contact-public-name", member_accounts=False)
    row = historic_anonymous_request(space, _product(space), name="Grace Hopper", verified=True)

    assert public_display_name(request=row) == "Grace Hopper"


def test_staff_can_read_the_contact_request():
    space = _space("contact-staff-read", member_accounts=False)
    row = historic_anonymous_request(space, _product(space), name="Grace Hopper", verified=True)
    manager = make_member("contact-staff-manager", space)

    response = authenticated_client(manager).get(f"/api/v1/admin/makerspace/{space.id}/pending-requests")

    assert response.status_code == 200, response.data
    rows = response.data["results"] if isinstance(response.data, dict) else response.data
    assert next(item for item in rows if item["id"] == row.pk)["requester_name"] == "Grace Hopper"
