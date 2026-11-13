"""Procurement intents remain tenant/type scoped and expire with source mutation."""
import pytest

from apps.integrations.models_contract import NotificationEnvelope
from apps.machines.notifications_p2_stock import eligible, notify
from apps.procurement.models import ToBuyItem
from tests.account_split.p1_helpers import staff
from tests.maintenance.helpers import make_machine_setup
from tests.return_helpers import make_space

pytestmark = pytest.mark.django_db


def test_received_intent_rechecks_source_revision_and_recipient_type_scope(monkeypatch):
    space, manager, machine, _ = make_machine_setup("recon-procurement")
    space.enabled_modules = sorted(set(space.enabled_modules) | {"procurement"})
    space.save(update_fields=["enabled_modules"])
    item = ToBuyItem.objects.create(makerspace=space, kind="printing", name="Material",
                                    machine_type=machine.machine_type, status="received")
    monkeypatch.setattr("apps.integrations.notification_outbox.enqueue", lambda pk: None)
    assert notify(item, "procurement_received").scheduled
    envelope = NotificationEnvelope.objects.get(recipient=manager, source_kind="machines.procurement")
    assert eligible(envelope)
    other = make_space("recon-procurement-other")
    foreign, _ = staff(other, "recon-procurement-foreign", "space_manager", access_status="active")
    envelope.recipient_id, envelope.recipient = foreign.pk, foreign
    assert not eligible(envelope)
    envelope.recipient_id, envelope.recipient = manager.pk, manager
    item.status = "cancelled"
    item.save(update_fields=["status", "updated_at"])
    assert not eligible(envelope)
