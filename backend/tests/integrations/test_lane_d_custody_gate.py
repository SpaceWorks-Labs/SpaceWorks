"""Custody control-plane SMTP survives a closed tenant source gate."""

import pytest as _legacy_pytest

_legacy_pytest.skip('Not in release 0.12.0: apps.backup.custody_alarms, apps.backup.tenant_exit_custody_alarms, apps.backup.models.ArchiveCustodyAlarmDelivery, apps.backup.models.MakerspaceArchiveCustodyState (+3 more)', allow_module_level=True)

import pytest

from apps.backup import custody_alarms, tenant_exit_custody_alarms
from apps.backup.models import (
    ArchiveCustodyAlarmDelivery,
    MakerspaceArchiveCustodyState,
    MakerspaceTenantExitCustodyState,
    TenantExitCustodyAlarmDelivery,
)
from apps.integrations.dispatch import dispatch_email
from apps.integrations.email_preferences import address_hash
from apps.integrations.models import EmailLog
from apps.integrations.models_suppression import EmailSuppression
from apps.tenant_migration.gate_errors import SourceMigrationGateClosed
from tests.backup.archive_custody_alarm_test_helpers import space as alarm_space
from tests.account_split.p1_helpers import staff as staff_account
from tests.events.lane_d_helpers import smtp
from tests.tenant_migration.source_gate_helpers import close_gate

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("kind", ["archive", "tenant_exit"])
@pytest.mark.parametrize("suppressed", [False, True])
def test_custody_alarm_uses_real_dispatch_under_closed_gate(monkeypatch, kind, suppressed):
    space = alarm_space("gate-" + kind, MakerspaceArchiveCustodyState.State.DEGRADED_ONE_RECIPIENT,
                        modules=())
    user, _ = staff_account(space, f"{space.slug}-manager", role="space_manager",
                            email=f"{space.slug}-manager@example.com")
    if kind == "archive":
        delivery_model = ArchiveCustodyAlarmDelivery
        deliver = custody_alarms.deliver_archive_custody_alarms
    else:
        MakerspaceTenantExitCustodyState.objects.create(
            makerspace=space, state="degraded_one_recipient", alarm_episode=1, alarm_revision=1,
        )
        delivery_model = TenantExitCustodyAlarmDelivery
        deliver = tenant_exit_custody_alarms.deliver_tenant_exit_custody_alarms
    if suppressed:
        EmailSuppression.objects.create(
            makerspace=space, address_hash=address_hash(space.pk, user.email), reason="bounce",
        )
    close_gate(space, user)
    send = smtp(monkeypatch)

    deliver(makerspace_id=space.pk)

    delivery = delivery_model.objects.get(makerspace=space, channel="tenant_email")
    log = EmailLog.objects.get(makerspace=space, stream="backup", event=kind + "_custody_alarm")
    if suppressed:
        assert log.status == "skipped" and log.error == "email_address_suppressed"
        assert delivery.status == "failed" and delivery.attempts == 1
        send.assert_not_called()
    else:
        assert log.status == delivery.status == "sent"
        assert log.attempts == 1 and delivery.attempts == 0
        send.assert_called_once()


@pytest.mark.parametrize("stream,event", [
    ("events", "archive_custody_alarm"),
    ("events", "tenant_exit_custody_alarm"),
    ("backup", "ordinary_update"),
    ("hardware", "return_reminder"),
])
def test_other_mail_still_obeys_source_gate(monkeypatch, stream, event):
    space = alarm_space("gate-ordinary", MakerspaceArchiveCustodyState.State.DEGRADED_ONE_RECIPIENT,
                        modules=("email",))
    user, _ = staff_account(space, f"{space.slug}-manager", role="space_manager",
                            email=f"{space.slug}-manager@example.com")
    close_gate(space, user)
    send = smtp(monkeypatch)
    with pytest.raises(SourceMigrationGateClosed):
        dispatch_email(makerspace=space, to_email=user.email, subject="Update", text_body="Body",
                       stream=stream, event=event, sync=True)
    send.assert_not_called()
