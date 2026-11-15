"""R2/R3: guest code issuance and consumption serialize with fundraising switches."""

from datetime import timedelta
from decimal import Decimal
from threading import Event, Thread
from time import monotonic, sleep
from unittest.mock import Mock

import pytest
from django.db import close_old_connections, connection, connections, transaction
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import DailyOtpEmailCounter, EmailVerificationChallenge, User
from apps.accounts.services_registration import GENERIC_CONFIRM_ERROR, _digest
from apps.audit.models import AuditLog
from apps.hardware_requests.contact_verification import email_key
from apps.makerspaces.anonymous_requesters import get_or_create_anonymous_requester
from apps.makerspaces.limits import reserve_platform_otp_quota
from apps.makerspaces.models import Makerspace
from apps.payments.donations import views_public
from apps.payments.donations.models import Donation, DonationCampaign, DonationPledge, DonorTaxDetail, Sponsor
from apps.payments.models import Payment, PaymentDocument
from tests.l18_local.helpers import CODE, setup, switch
from tests.modules.switch_matrix_object_helpers import no_domain_writes
from tests.money_modes.helpers import OFFLINE, set_mode
from tests.payments.test_fundraising_mutations_cx14 import snapshot

pytestmark = pytest.mark.django_db
EMAIL = "guest@example.test"
BODY = {"donor_email": EMAIL}


def code_world(existing, monkeypatch):
    space, manager, _donor = setup("cx14-public-code", "finance.sponsors")
    DonationCampaign.objects.create(makerspace=space, name="Retained", slug="retained", currency="inr")
    Sponsor.objects.create(makerspace=space, name="Retained sponsor", created_by=manager)
    if existing:
        principal = get_or_create_anonymous_requester(space)
        EmailVerificationChallenge.objects.create(
            user=principal, email=email_key(space, EMAIL), code_digest=_digest(CODE),
            expires_at=timezone.now() + timedelta(minutes=5), failed_attempts=2,
            last_sent_at=timezone.now() - timedelta(minutes=2))
    else:
        assert space.anonymous_requester_id is None
    DailyOtpEmailCounter.objects.get_or_create(day=timezone.now().date(), defaults={"count": 7})
    dispatch = Mock(return_value=True)
    quota = Mock(wraps=reserve_platform_otp_quota)
    monkeypatch.setattr("apps.integrations.email.send_email_verification_otp", dispatch)
    monkeypatch.setattr("apps.makerspaces.limits.reserve_platform_otp_quota", quota)
    monkeypatch.setattr("apps.hardware_requests.contact_verification._generate_otp", lambda: CODE)
    url = reverse("public-donation-email-code", kwargs={"makerspace_slug": space.slug})
    return space, APIClient(), url, dispatch, quota


def code_snapshot(space):
    """Retain complete verification/principal/quota/audit rows, including existing data."""
    return {
        "domain": snapshot(space),
        "principal_link": Makerspace.objects.values_list("anonymous_requester_id", flat=True).get(pk=space.pk),
        **{model._meta.label: list(model.objects.order_by("pk").values()) for model in
           (User, EmailVerificationChallenge, DailyOtpEmailCounter, AuditLog, DonationPledge, DonorTaxDetail,
            PaymentDocument)},
    }


@pytest.mark.parametrize("existing", [False, True], ids=["new-principal", "existing-principal"])
@pytest.mark.parametrize("mail_sent", [False, True], ids=["delivery-failed", "delivered"])
def test_public_code_off_refuses_before_writes_or_mail_and_on_restores(existing, mail_sent, monkeypatch):
    space, api, url, dispatch, quota = code_world(existing, monkeypatch)
    dispatch.return_value = mail_sent
    switch(space, "finance.donations", on=False)
    before = code_snapshot(space)
    with no_domain_writes():
        refused = api.post(url, BODY, format="json")
    assert refused.status_code == 404, refused.content
    assert refused.json()["code"] == "feature_disabled"
    assert code_snapshot(space) == before
    dispatch.assert_not_called()
    quota.assert_not_called()

    switch(space, "finance.donations")
    restored = api.post(url, BODY, format="json")
    assert restored.status_code == 202, restored.content
    assert restored.content == b""  # Delivery outcome remains private.
    dispatch.assert_called_once_with(EMAIL, CODE)
    quota.assert_called_once_with()
    space.refresh_from_db()
    assert space.anonymous_requester_id is not None
    assert User.objects.count() == len(before[User._meta.label]) + int(not existing)
    if existing:
        assert space.anonymous_requester_id == before["principal_link"]
    challenges = EmailVerificationChallenge.objects.filter(user_id=space.anonymous_requester_id)
    assert challenges.count() == int(existing) + 1
    active = challenges.get(consumed_at__isnull=True)
    assert (active.email, active.code_digest, active.failed_attempts) == (email_key(space, EMAIL), _digest(CODE), 0)
    if existing:
        previous = challenges.exclude(pk=active.pk).get()
        assert previous.consumed_at is not None
        assert previous.failed_attempts == 2
    assert snapshot(space) == before["domain"]
    assert AuditLog.objects.count() == len(before[AuditLog._meta.label]) + 1
    audit = AuditLog.objects.get(makerspace=space, action="request.contact_code_sent")
    assert audit.actor_id is None
    assert audit.meta == {"email_hash": email_key(space, EMAIL), "email_sent": mail_sent}

    after = code_snapshot(space)
    with no_domain_writes():
        replay = api.post(url, BODY, format="json")
    assert replay.status_code == 429, replay.content
    assert replay.json()["code"] == "throttled"
    assert code_snapshot(space) == after
    dispatch.assert_called_once_with(EMAIL, CODE)
    quota.assert_called_once_with()


def wait_for_disable(space, api, url, body, key, monkeypatch):
    assert connection.vendor == "postgresql"
    original = views_public.public_space
    looked_up, resume, finished = Event(), Event(), Event()
    results, errors, pids = [], [], []
    before = code_snapshot(space)
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_backend_pid()")
        disabler_pid = cursor.fetchone()[0]

    def pause_after_lookup(*args, **kwargs):
        found = original(*args, **kwargs)  # Real public visibility and initial ON check.
        with connections["default"].cursor() as cursor:
            cursor.execute("SELECT pg_backend_pid()")
            pids.append(cursor.fetchone()[0])
        looked_up.set()
        assert resume.wait(8), "Disable never reached its locked update"
        return found

    monkeypatch.setattr(views_public, "public_space", pause_after_lookup)

    def request():
        close_old_connections()
        db = connections["default"]
        try:
            with db.cursor() as cursor:
                cursor.execute("SET lock_timeout = '8s'")
            # The real handler runs with every SQL write attempt forbidden after
            # authentication, even if its transaction would roll that write back.
            with no_domain_writes():
                response = api.post(url, body, format="json")
            results.append((response.status_code, response.json().get("code")))
        except BaseException as exc:
            errors.append(exc)
        finally:
            db.close()
            finished.set()

    thread = Thread(target=request, daemon=True)
    thread.start()
    try:
        assert looked_up.wait(6), errors
        with transaction.atomic():
            locked = Makerspace.objects.select_for_update().get(pk=space.pk)
            locked.enabled_features = sorted(set(locked.enabled_features) - {key})
            locked.save(update_fields=["enabled_features"])
            resume.set()
            blockers = []
            deadline = monotonic() + 3
            while monotonic() < deadline and not finished.is_set():
                with connection.cursor() as cursor:
                    cursor.execute("SELECT pg_blocking_pids(%s)", [pids[0]])
                    blockers = cursor.fetchone()[0]
                if disabler_pid in blockers:
                    break
                sleep(0.01)
            assert disabler_pid in blockers, ("Public handler did not wait for the switch lock", errors, results)
            assert not finished.is_set()
        thread.join(timeout=10)  # OFF commits before the handler can acquire its fresh fence.
    finally:
        resume.set()
        thread.join(timeout=10)
    assert not thread.is_alive()
    assert errors == []
    assert results == [(404, "feature_disabled")]
    assert code_snapshot(space) == before
    monkeypatch.setattr(views_public, "public_space", original)


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("existing", [False, True], ids=["new-principal", "existing-principal"])
def test_public_code_waits_for_disable_then_refuses_before_writes_or_mail(existing, monkeypatch):
    space, api, url, dispatch, quota = code_world(existing, monkeypatch)
    wait_for_disable(space, api, url, BODY, "finance.donations", monkeypatch)
    dispatch.assert_not_called()
    quota.assert_not_called()


def creation_world(kind, monkeypatch):
    space, api, _, dispatch, quota = code_world(True, monkeypatch)
    switch(space, "finance.recurring_donations")
    set_mode(space, "donations", OFFLINE)
    checkout, notify = Mock(return_value=""), Mock()
    payment_notice, document_notice = Mock(), Mock()
    monkeypatch.setattr("apps.payments.donations.services.checkout_url", checkout)
    monkeypatch.setattr("apps.payments.donations.notices._send", notify)
    monkeypatch.setattr("apps.payments.notifications.notify_payment", payment_notice)
    monkeypatch.setattr("apps.payments.notifications_p2.notify_document", document_notice)
    route = "public-donations" if kind == "gift" else "public-donation-pledges"
    url = reverse(route, kwargs={"makerspace_slug": space.slug})
    body = {"amount": "25", "donor_name": "Guest", "donor_email": EMAIL, "email_code": CODE}
    if kind == "pledge":
        body["interval"] = "monthly"
    return space, api, url, body, (dispatch, quota, checkout, notify, payment_notice, document_notice)


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("kind,key", [
    ("gift", "finance.donations"), ("pledge", "finance.donations"),
    ("pledge", "finance.recurring_donations"),
])
def test_guest_creation_waits_for_disable_without_spending_code_and_on_restores(kind, key, monkeypatch):
    space, api, url, body, effects = creation_world(kind, monkeypatch)
    before = code_snapshot(space)
    wait_for_disable(space, api, url, body, key, monkeypatch)
    for effect in effects:
        effect.assert_not_called()
    space.refresh_from_db()
    switch(space, key)
    restored = api.post(url, body, format="json")
    assert restored.status_code == 201, restored.content
    challenge = EmailVerificationChallenge.objects.get(user_id=space.anonymous_requester_id)
    expected = dict(before[EmailVerificationChallenge._meta.label][0], consumed_at=challenge.consumed_at)
    assert challenge.consumed_at is not None
    assert EmailVerificationChallenge.objects.values().get(pk=challenge.pk) == expected
    assert list(User.objects.order_by("pk").values()) == before[User._meta.label]
    assert Makerspace.objects.get(pk=space.pk).anonymous_requester_id == before["principal_link"]
    model, action = (Donation, "donation.created") if kind == "gift" else (DonationPledge, "pledge.created")
    assert model.objects.filter(makerspace=space).count() == 1
    row = model.objects.get(pk=restored.json()["id"])
    assert (row.donor_id, row.donor_name, row.donor_email, row.amount) == (None, "Guest", EMAIL, Decimal("25"))
    assert row.created_by_id == space.anonymous_requester_id
    assert (Donation.objects.count(), DonationPledge.objects.count()) == (int(kind == "gift"), int(kind == "pledge"))
    payments = Payment.objects.filter(makerspace=space)
    assert payments.count() == int(kind == "gift")
    if kind == "gift":
        payment = payments.get()
        assert (payment.subject_type, payment.subject_id, payment.amount, payment.provider, payment.status) == (
            "donation", row.pk, Decimal("25"), "unclaimed", "pending")
        effects[2].assert_called_once_with(payment)
        effects[4].assert_called_once_with(payment, "charge_raised")
        document = PaymentDocument.objects.get(payment=payment, kind="bill")
        effects[5].assert_called_once_with(document, initial=True)
    else:
        effects[2].assert_not_called()
        effects[4].assert_not_called()
        effects[5].assert_not_called()
    expected_actions = [action] + (["payment.created", "payment.document_issued"] if kind == "gift" else [])
    new_audits = AuditLog.objects.exclude(pk__in=[row["id"] for row in before[AuditLog._meta.label]])
    assert sorted(new_audits.values_list("action", flat=True)) == sorted(expected_actions)
    assert AuditLog.objects.filter(makerspace=space, action=action).count() == 1
    for effect in (effects[0], effects[1], effects[3]):
        effect.assert_not_called()


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("kind", ["gift", "pledge"])
def test_enabled_guest_wrong_code_commits_exactly_one_failed_attempt_and_audit(kind, monkeypatch):
    space, api, url, body, effects = creation_world(kind, monkeypatch)
    before = code_snapshot(space)
    refused = api.post(url, {**body, "email_code": "000000"}, format="json")
    assert refused.status_code == 400, refused.content
    assert refused.data["email_code"].code == "invalid"
    assert refused.json() == {"email_code": GENERIC_CONFIRM_ERROR}
    before[EmailVerificationChallenge._meta.label][0]["failed_attempts"] += 1
    audit = AuditLog.objects.get(makerspace=space, action="request.contact_code_failed")
    assert audit.actor_id is None
    assert audit.meta == {"email_hash": email_key(space, EMAIL)}
    assert AuditLog.objects.count() == len(before[AuditLog._meta.label]) + 1
    before[AuditLog._meta.label].append(AuditLog.objects.values().get(pk=audit.pk))
    assert code_snapshot(space) == before  # Only that attempt and audit committed; code is still usable.
    for effect in effects:
        effect.assert_not_called()
