"""Pre-upgrade EmailLog digests retain address boundaries across changes and SMTP retries."""

import pytest

from apps.accounts.models import User
from apps.integrations.delivery_content import content, render
from apps.integrations.delivery_sources import DeliverySource, SOURCES, prepare
from apps.integrations.dispatch_delivery import _deliver
from apps.integrations.dispatch_outbox import dispatch_email
from apps.integrations.models import EmailLog
from tests.bookings.bk_d_reminder_helpers import release, reminder

pytestmark = pytest.mark.django_db(transaction=True)
NEW_ADDRESS = "reverified-owner@example.test"


def _change_email(user, clock, *, verified=True):
    User.objects.filter(pk=user.pk).update(
        email=NEW_ADDRESS, email_verified_at=clock[0] if verified else None,
    )


def _fail_first_attempt(summary, send):
    send.side_effect = RuntimeError("temporary SMTP failure")
    _deliver(summary)
    assert summary.status == "failed" and summary.attempts == 1
    send.assert_called_once()
    send.reset_mock()
    send.side_effect = None


@pytest.mark.parametrize("retry", [False, True])
@pytest.mark.parametrize("address_state", ["unchanged", "reverified", "unverified"])
def test_assembled_booking_digest_revalidates_recipient_before_smtp(monkeypatch, retry, address_state):
    world, clock, due, send, child, _ = reminder(monkeypatch, mode="digest")
    tenant, _, _, resource, _, owner, _ = world
    assert "membership" not in tenant.enabled_modules
    assert child.status == "pending" and not send.called
    release(clock, due)
    summary = EmailLog.objects.get(makerspace=tenant, source_kind="notification_digest")
    assert summary.to_email == owner.email
    assert summary.source_metadata["entries"] == [child.pk]
    child.refresh_from_db()
    assert child.error == "included_in_daily_digest"
    if retry:
        _fail_first_attempt(summary, send)
        # Exercise worker reload as well as reuse of an instance on retry.
        summary = EmailLog.objects.get(pk=summary.pk)
    if address_state != "unchanged":
        _change_email(owner, clock, verified=address_state == "reverified")
    # A verified new address is still valid for the child reminder itself.
    # Only the assembled summary's different address makes inclusion unsafe.
    assert prepare(child) is (address_state != "unverified")
    if address_state == "reverified":
        assert content(child).to_email == NEW_ADDRESS
    _deliver(summary)
    summary.refresh_from_db()
    if address_state == "unchanged":
        assert summary.status == "sent"
        send.assert_called_once()
        message = send.call_args.args[0]
        assert message.to == [owner.email]
        assert resource.name in message.body
    else:
        assert summary.status == "skipped"
        assert summary.error == "delivery_source_no_longer_eligible"
        assert content(summary).text_body == ""
        send.assert_not_called()
    assert summary.attempts == int(retry) + int(address_state == "unchanged")
    assert summary.source_metadata["entries"] == [child.pk]


def test_email_change_before_digest_assembly_uses_reverified_address(monkeypatch):
    world, clock, due, send, child, _ = reminder(monkeypatch, mode="digest")
    tenant, _, _, resource, _, owner, _ = world
    _change_email(owner, clock)
    release(clock, due)
    summary = EmailLog.objects.get(makerspace=tenant, source_kind="notification_digest")
    assert summary.to_email == NEW_ADDRESS
    assert summary.source_metadata["entries"] == [child.pk]
    _deliver(summary)
    assert summary.status == "sent"
    send.assert_called_once()
    assert send.call_args.args[0].to == [NEW_ADDRESS]
    assert resource.name in send.call_args.args[0].body


@pytest.mark.parametrize("retry", [False, True])
def test_mixed_digest_keeps_only_entries_valid_for_summary_address(monkeypatch, retry):
    world, clock, due, send, child, _ = reminder(monkeypatch, mode="digest")
    tenant, _, _, resource, _, owner, _ = world

    def prepare_survivor(log):
        # Another source still authorizes its entry for this summary address.
        render(log, to_email=owner.email, subject="Surviving update", text_body="Still authorized")
        return True

    monkeypatch.setitem(SOURCES, "test_digest_survivor", DeliverySource(prepare_survivor))
    survivor = dispatch_email(
        makerspace=tenant, recipient_id=owner.pk, to_email=owner.email,
        feature="bookings", stream="bookings", event="created", audience="requester",
        subject="Surviving update", text_body="Still authorized",
        source_kind="test_digest_survivor", sync=True,
    )
    assert survivor.error.startswith("deferred:digest:")
    release(clock, due)
    summary = EmailLog.objects.get(makerspace=tenant, source_kind="notification_digest")
    assert set(summary.source_metadata["entries"]) == {child.pk, survivor.pk}
    if retry:
        _fail_first_attempt(summary, send)
    _change_email(owner, clock)
    _deliver(summary)
    assert summary.status == "sent"
    send.assert_called_once()
    message = send.call_args.args[0]
    assert message.to == [owner.email]
    assert message.body == "Surviving update\nStill authorized"
    assert resource.name not in message.body
