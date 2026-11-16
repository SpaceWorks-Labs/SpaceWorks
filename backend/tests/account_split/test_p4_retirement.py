import pytest
from django.db import connection, transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.audit.verification import classify_audit_row, AuditMacStatus
from apps.audit.integrity import verify_audit_integrity
from apps.makerspaces.lifecycle_purge import purge
from apps.makerspaces.models import Makerspace, MakerspaceMembership
from apps.tenant_migration.admission import compute_pending_closure
from tests.audit_batch_helpers import MemoryAnchorSink, activate_and_seal
from .p1_helpers import staff
from .p4_auth_helpers import staff_auth_history

pytestmark = pytest.mark.django_db(transaction=True)


def test_purge_retires_nobody_and_keeps_global_auth_audits_and_attestation(settings):
    """One account per person (U-C): a tenant purge deletes the space's staff-track rows and
    keeps the person, their credentials and their global authentication history."""
    settings.MANAGED_POSTGRES = True
    settings.AUDIT_ATTESTATION_DEPLOYMENT_ID = "p4-retirement-audit"
    space = Makerspace.objects.create(name="Retirement", slug="p4-retirement")
    operator, _ = staff(space, email="staff-pii@example.test", first_name="Private", phone="+15550123456")
    owner = User.objects.create_superuser("p4-owner", "p4-owner@example.test", "owner-password")
    sink = MemoryAnchorSink()
    activate_and_seal(None, sink)
    events = staff_auth_history(operator, space, settings)
    _key, batch = activate_and_seal(None, sink)
    original = list(AuditLog.objects.filter(pk__in=[event.pk for event in events]).values())
    space.archived_at = timezone.now()
    space.save(update_fields=["archived_at"])
    purge(space, owner)
    operator.refresh_from_db()
    assert not Makerspace.objects.filter(pk=space.pk).exists()
    assert operator.account_kind == "member" and operator.retired_at is None and operator.is_active
    assert operator.email == "staff-pii@example.test" and operator.first_name == "Private"
    assert not MakerspaceMembership.all_tracks.filter(user=operator).exists()
    assert list(AuditLog.objects.filter(pk__in=[event.pk for event in events]).values()) == original
    for event in events:
        event.refresh_from_db()
        assert event.actor_id == operator.pk
        assert classify_audit_row(event) == AuditMacStatus.ATTESTED
    assert set(batch.leaves.filter(audit_log_id__in=[event.pk for event in events]).values_list(
        "audit_log_id", flat=True)) == {event.pk for event in events}
    assert verify_audit_integrity(sink=sink) is None


def test_export_closure_includes_owned_staff_and_drops_them_with_their_staff_row():
    space = Makerspace.objects.create(name="Export staff", slug="p4-staff-export")
    operator, membership = staff(space, email="staff-export@example.test")
    assert str(operator.pk) in {str(row["id"]) for row in compute_pending_closure(space)["identities"]}
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("SELECT set_config('app.tenant_purge_makerspace_id', %s, true)", [str(space.pk)])
        MakerspaceMembership.all_tracks.filter(pk=membership.pk).delete()
    assert str(operator.pk) not in {str(row["id"]) for row in compute_pending_closure(space)["identities"]}
