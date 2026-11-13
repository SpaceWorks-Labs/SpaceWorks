"""Migration 0040: nobody loses access when certifications become machine access grants (decision 319)."""
from datetime import timedelta
from importlib import import_module

import pytest
from django.apps import apps
from django.utils import timezone

from apps.machines.access_grants import can_use
from apps.machines.models import (
    CertificationGrant, CertificationType, GuestCertificationGrant, Machine, MachineAccessGrant,
)
from tests.machines.certification_helpers import _member
from tests.parity_0120.machine_access.helpers import world

pytestmark = pytest.mark.django_db

migration = import_module("apps.machines.migrations.0040_certifications_to_access_grants")


def gated_world():
    w = world()
    w.space.enabled_features = sorted({*(w.space.enabled_features or []), "machines.certifications"})
    w.space.save(update_fields=["enabled_features"])
    required = CertificationType.objects.create(makerspace=w.space, machine_type=w.kind, name="Laser induction",
                                                is_required_for_service=True)
    return w, required


def run():
    migration.convert(apps, None)


def test_certified_members_get_a_type_grant_and_keep_their_expiry():
    w, required = gated_world()
    expiry = timezone.now() + timedelta(days=60)
    CertificationGrant.objects.create(certification_type=required, membership=w.membership, expires_at=expiry)
    uncertified, _ = _member(w.space, "untrained")
    run()
    row = MachineAccessGrant.objects.get(member=w.member)
    assert row.machine_type_id == w.kind.pk and row.expires_at == expiry and row.source == "migration"
    for machine in (w.laser, w.laser2):
        machine.refresh_from_db()
        assert can_use(w.member, machine) == (True, None)
        assert can_use(uncertified, machine)[0] is False


def test_expired_or_revoked_certifications_convert_to_nothing():
    w, required = gated_world()
    CertificationGrant.objects.create(certification_type=required, membership=w.membership,
                                      expires_at=timezone.now() - timedelta(days=1))
    run()
    assert not MachineAccessGrant.objects.filter(member=w.member).exists()


def test_every_required_type_of_one_purpose_must_be_held():
    """Decision 335(a): meeting ONE gated purpose is enough; within a purpose every type is still needed."""
    w, required = gated_world()
    second = CertificationType.objects.create(makerspace=w.space, machine_type=w.kind, name="Laser safety",
                                              is_required_for_service=True)
    CertificationGrant.objects.create(certification_type=required, membership=w.membership)
    run()
    assert not MachineAccessGrant.objects.filter(member=w.member).exists()
    CertificationGrant.objects.create(certification_type=second, membership=w.membership)
    run()
    assert MachineAccessGrant.objects.filter(member=w.member).count() == 1


def test_ungated_machines_become_open_to_all_members_and_gated_types_do_not():
    w, _required = gated_world()
    run()
    for machine in (w.laser, w.laser2, w.mill):
        machine.refresh_from_db()
    assert w.laser.open_to_all_members is False and w.laser2.open_to_all_members is False
    assert w.mill.open_to_all_members is True


def test_a_space_that_never_turned_gating_on_opens_every_machine():
    w = world()
    CertificationType.objects.create(makerspace=w.space, machine_type=w.kind, name="Unused", is_required_for_service=True)
    run()
    assert not Machine.objects.filter(makerspace=w.space, open_to_all_members=False).exists()


def test_guest_certifications_convert_and_the_run_is_idempotent():
    w, required = gated_world()
    GuestCertificationGrant.objects.create(makerspace=w.space, certification_type=required, user=w.member)
    run()
    run()
    assert MachineAccessGrant.objects.filter(member=w.member, machine_type=w.kind).count() == 1
    assert CertificationType.objects.filter(pk=required.pk).exists()
    assert GuestCertificationGrant.objects.filter(user=w.member).exists()
