"""SWITCH-MATRIX: payments x email x charges.* with every charging area, and the mid-flow cases.

Every charging domain (bookings, events, machines, membership) in all four states of (payments module, email
module), with charge tracking on and off:

* a recorded charge is never lost when the rail or the mail goes off, it stays pending and visible to the member
  (the ledger is core), with no 5xx anywhere;
* nothing is sent while `email` is off, and a message queued before the switch went off is skipped at delivery,
  terminally (never resent when email comes back);
* switching the rail off under a live charge keeps the row byte-identical, and both off together changes nothing.
"""

import pytest
from django.core import mail
from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.integrations.dispatch import dispatch_email
from apps.integrations.dispatch_delivery import _deliver
from apps.integrations.models import EmailLog
from apps.makerspaces.module_install import install_module, uninstall_module
from apps.payments.availability import charge_tracking_enabled, online_payments_enabled
from apps.payments.models import Payment
from tests.modules.test_offstate_money import DOMAIN_MODULES, _configured_space, _invoke_charge_caller
from tests.return_helpers import make_member

pytestmark = pytest.mark.django_db

DOMAINS = tuple(DOMAIN_MODULES)
STATES = [(p, e) for p in (True, False) for e in (True, False)]


def _space(slug, domain, payments, email, tracked=True):
    space = _configured_space(slug, domain, payments_on=payments)
    if email:
        install_module(space, "email")
    if not tracked:
        space.enabled_features = [k for k in space.enabled_features if not k.startswith("charges.")]
        space.save(update_fields=["enabled_features"])
    space.refresh_from_db()
    return space


def _send(space):
    return dispatch_email(
        makerspace=space, to_email="payer@example.test", subject="Payment due", text_body="You owe money.",
        stream="billing", event="payment_due", audience="member", sync=True,
    )


def _history(space, member):
    client = APIClient(raise_request_exception=False)
    client.force_authenticate(member)
    return client.get(reverse("member-payment-history", args=[space.pk]))


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
@pytest.mark.parametrize("payments,email", STATES)
@pytest.mark.parametrize("domain", DOMAINS)
def test_charge_is_recorded_and_visible_and_mail_follows_only_the_email_switch(domain, payments, email):
    slug = f"smm-{domain}-{int(payments)}{int(email)}"
    space = _space(slug, domain, payments, email)
    member = make_member(f"{slug}-m", space, membership_role="custom", role=User.Role.REQUESTER)

    subject, charge = _invoke_charge_caller(domain, space, member)

    assert charge_tracking_enabled(space, domain) is True
    assert online_payments_enabled(space, domain) is payments
    assert charge is not None and charge.status == Payment.Status.PENDING
    if not payments:
        assert charge.checkout_url == "" and charge.online_rail is None
    assert type(subject).objects.filter(pk=subject.pk).exists()
    seen = _history(space, member)
    assert seen.status_code == 200, seen.status_code
    sent = _send(space)
    if email:
        assert sent.status == EmailLog.Status.SENT and len(mail.outbox) == 1
    else:
        assert sent.status == EmailLog.Status.SKIPPED and mail.outbox == []
    # Mail never touches the debt.
    charge.refresh_from_db()
    assert charge.status == Payment.Status.PENDING


@pytest.mark.parametrize("payments,email", STATES)
@pytest.mark.parametrize("domain", DOMAINS)
def test_charges_off_records_nothing_whatever_the_rail_and_the_mail(domain, payments, email):
    slug = f"smt-{domain}-{int(payments)}{int(email)}"
    space = _space(slug, domain, payments, email, tracked=False)
    member = make_member(f"{slug}-m", space, membership_role="custom", role=User.Role.REQUESTER)

    subject, charge = _invoke_charge_caller(domain, space, member)

    assert charge is None and not Payment.objects.filter(makerspace=space).exists()
    assert type(subject).objects.filter(pk=subject.pk).exists()
    assert _history(space, member).status_code == 200


@pytest.mark.parametrize("domain", DOMAINS)
def test_switching_the_rail_and_the_mail_off_under_a_live_charge_changes_nothing_about_the_debt(domain):
    slug = f"smb-{domain}"
    space = _space(slug, domain, True, True)
    member = make_member(f"{slug}-m", space, membership_role="custom", role=User.Role.REQUESTER)
    _subject, charge = _invoke_charge_caller(domain, space, member)

    def row():
        return Payment.objects.filter(pk=charge.pk).values_list("status", "amount", "subject_type", "subject_id", "member_id").get()

    before = row()
    uninstall_module(space, "email")
    assert row() == before
    uninstall_module(space, "payments")
    assert row() == before and Payment.objects.filter(makerspace=space).count() == 1
    assert _history(space, member).status_code == 200
    install_module(space, "payments")
    install_module(space, "email")
    assert row() == before


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_a_message_queued_before_email_went_off_is_skipped_at_delivery_and_never_resent():
    space = _space("smq-queued", "events", True, True)
    queued = dispatch_email(
        makerspace=space, to_email="payer@example.test", subject="Payment due", text_body="You owe money.",
        stream="billing", event="payment_due", audience="member", sync=False,
    )
    assert queued.status == EmailLog.Status.PENDING and mail.outbox == []

    uninstall_module(space, "email")
    _deliver(EmailLog.objects.get(pk=queued.pk))

    done = EmailLog.objects.get(pk=queued.pk)
    assert done.status == EmailLog.Status.SKIPPED and mail.outbox == []
    install_module(space, "email")
    _deliver(EmailLog.objects.get(pk=queued.pk))
    assert EmailLog.objects.get(pk=queued.pk).status == EmailLog.Status.SKIPPED and mail.outbox == []


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_a_duty_of_care_message_still_sends_with_email_and_payments_both_off():
    space = _space("smq-duty", "events", False, False)
    sent = dispatch_email(
        makerspace=space, to_email="borrower@example.test", subject="Overdue", text_body="Please return.",
        stream="hardware", event="return_reminder", audience="member", sync=True,
    )
    assert sent.status == EmailLog.Status.SENT and len(mail.outbox) == 1


def test_in_app_notices_still_appear_with_email_and_payments_off(django_capture_on_commit_callbacks):
    from apps.notifications.emit import emit_notification
    from apps.notifications.models import Notification

    space = _space("smq-inapp", "events", False, False)
    install_module(space, "notifications")
    with django_capture_on_commit_callbacks(execute=True):
        emit_notification(space, title="Payment due", event="payment.due")
    assert Notification.objects.filter(makerspace=space, title="Payment due").count() == 1
    assert mail.outbox == []
