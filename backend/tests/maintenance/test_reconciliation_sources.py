"""A log's operator authority and a recipient's type scope are different checks."""
import pytest

from apps.integrations.models_contract import NotificationEnvelope
from apps.machines.models import MachineOperator
from apps.machines.notifications_p2_maintenance import eligible, notify
from apps.makerspaces.models import MakerspaceMembership
from apps.maintenance.models import MaintenanceLog
from tests.maintenance.helpers import make_machine_setup
from tests.return_helpers import make_user

pytestmark = pytest.mark.django_db


def test_operate_only_log_author_is_valid_until_the_machine_grant_is_revoked(monkeypatch):
    space, manager, machine, _ = make_machine_setup("recon-maintenance")
    user = make_user("recon-maintenance-operator", access_status="active")
    MakerspaceMembership.objects.create(makerspace=space, user=user, role="custom",
                                        assigned_role=space.roles.get(slug="member"))
    grant = MachineOperator.objects.create(machine=machine, user=user, access_level="operate")
    log = MaintenanceLog.objects.create(machine=machine, performed_by=user,
                                        summary="Private summary", parts_note="Private parts")
    monkeypatch.setattr("apps.integrations.notification_outbox.enqueue", lambda pk: None)
    assert notify(log, "logged").scheduled
    envelope = NotificationEnvelope.objects.get(recipient=manager, source_kind="machines.maintenance")
    assert eligible(envelope)
    assert envelope.context["machine.id"] == machine.pk
    assert "Private" not in str(envelope.context)
    grant.delete()
    assert not eligible(envelope)
