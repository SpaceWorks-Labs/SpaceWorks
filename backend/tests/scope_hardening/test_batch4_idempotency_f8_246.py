"""Decision 246 (lane F8): the 0.12.0 scoping reads are repeatable and write nothing (224 IDM)."""
import pytest

from apps.audit.area_scope import scope_audit_rows
from apps.audit.models import AuditLog
from apps.integrations.link_webhooks import link_changes
from apps.machines.models import CertificationType
from apps.machines.reports_certifications import build_certification_coverage
from tests.fixed_roles.helpers import staff_account
from tests.maintenance.l16_helpers import world

pytestmark = pytest.mark.django_db


def _rows(w):
    named = AuditLog.objects.create(
        makerspace=w.space, actor=w.manager, action="service_state.changed", target_type="machines.machine",
        target_id=str(w.machine.pk), meta={"subject_type": "machine", "machine_id": w.machine.pk})
    bare = AuditLog.objects.create(
        makerspace=w.space, actor=w.manager, action="service_state.changed", target_type="machines.machine",
        target_id="0", meta={"subject_type": "machine"})
    return named, bare


def test_audit_scoping_is_repeatable_and_a_read_never_writes_audit_rows():
    w = world("f8-224-audit")
    named, bare = _rows(w)
    laser = staff_account(w.space, "f8-224-laser", "machine_manager", machine_types=[w.kind])
    before = AuditLog.objects.count()
    pks = [named.pk, bare.pk]
    first = set(scope_audit_rows(laser, AuditLog.objects.filter(pk__in=pks)).values_list("pk", flat=True))
    second = set(scope_audit_rows(laser, AuditLog.objects.filter(pk__in=pks)).values_list("pk", flat=True))
    assert first == second == {named.pk}
    assert AuditLog.objects.count() == before


def test_scoping_the_same_queryset_twice_does_not_widen_or_narrow_it():
    w = world("f8-224-twice")
    named, bare = _rows(w)
    boss = w.manager
    once = scope_audit_rows(boss, AuditLog.objects.filter(pk__in=[named.pk, bare.pk]))
    twice = scope_audit_rows(boss, once)
    assert set(once.values_list("pk", flat=True)) == set(twice.values_list("pk", flat=True))


def test_certification_coverage_is_repeatable_and_creates_no_rows():
    w = world("f8-224-cert")
    CertificationType.objects.create(makerspace=w.space, machine_type=w.kind, name="Laser induction")
    CertificationType.objects.create(makerspace=w.space, machine_type=w.other_kind, name="CNC induction")
    laser = staff_account(w.space, "f8-224-cert-laser", "machine_manager", machine_types=[w.kind])
    before = CertificationType.objects.count()
    a = build_certification_coverage(w.space.id, actor=laser).records
    b = build_certification_coverage(w.space.id, actor=laser).records
    assert a == b and {row["machine_type"] for row in a} == {"Laser"}
    assert CertificationType.objects.count() == before


def test_link_change_mapping_is_pure_a_repeat_or_a_no_change_emits_nothing_new():
    assert link_changes("event_loan", None, 5, False) == link_changes("event_loan", None, 5, False)
    assert link_changes("event_loan", 5, 5, False) == []  # re-saving the same link: no webhook
    assert link_changes("event_loan", 5, None, True) == [("event_loan_unlinked", 5)]
    assert link_changes("event_loan", None, None, True) == []  # unlinking twice: nothing the second time
