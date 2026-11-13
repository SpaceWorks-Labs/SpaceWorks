"""Migration 0040, decision 335(a): purpose-specific certification requirements convert per purpose.

Before decision 319 a machine type could require one certification for running it (service) and a
different one for booking it. A member who met EITHER purpose's requirements keeps access; a member who
met neither does not; a purpose nobody was gated for qualifies nobody.
"""
from datetime import timedelta
from importlib import import_module

import pytest
from django.apps import apps
from django.utils import timezone

from apps.machines.models import CertificationGrant, CertificationType, MachineAccessGrant
from tests.machines.certification_helpers import _member
from tests.parity_0120.machine_access.helpers import world

pytestmark = pytest.mark.django_db

migration = import_module("apps.machines.migrations.0040_certifications_to_access_grants")


def _gated():
    w = world()
    w.space.enabled_features = sorted({*(w.space.enabled_features or []), "machines.certifications"})
    w.space.save(update_fields=["enabled_features"])
    service = CertificationType.objects.create(makerspace=w.space, machine_type=w.kind, name="Run the laser",
                                               is_required_for_service=True)
    booking = CertificationType.objects.create(makerspace=w.space, machine_type=w.kind, name="Book the laser",
                                               is_required_for_booking=True)
    return w, service, booking


def run():
    migration.convert(apps, None)


def test_service_only_holder_keeps_access_when_booking_needed_something_else():
    w, service, _booking = _gated()
    CertificationGrant.objects.create(certification_type=service, membership=w.membership)
    run()
    row = MachineAccessGrant.objects.get(member=w.member)
    assert row.machine_type_id == w.kind.pk and row.source == "migration" and row.note == migration.NOTE


def test_booking_only_holder_keeps_access_too():
    w, _service, booking = _gated()
    CertificationGrant.objects.create(certification_type=booking, membership=w.membership)
    run()
    assert MachineAccessGrant.objects.filter(member=w.member, machine_type=w.kind).count() == 1


def test_a_member_who_met_no_purpose_gets_nothing():
    w, _service, _booking = _gated()
    stranger, _ = _member(w.space, "no-certs")
    run()
    assert not MachineAccessGrant.objects.filter(member__in=[w.member, stranger]).exists()


def test_an_unrestricted_purpose_qualifies_nobody():
    """Only service was gated; booking needed nothing, so it is not a purpose the type was gated for."""
    w = world()
    w.space.enabled_features = sorted({*(w.space.enabled_features or []), "machines.certifications"})
    w.space.save(update_fields=["enabled_features"])
    service = CertificationType.objects.create(makerspace=w.space, machine_type=w.kind, name="Run the laser",
                                               is_required_for_service=True)
    holder, holder_membership = _member(w.space, "holder")
    CertificationGrant.objects.create(certification_type=service, membership=holder_membership)
    run()
    assert MachineAccessGrant.objects.filter(member=holder).count() == 1
    assert not MachineAccessGrant.objects.filter(member=w.member).exists()
    w.laser.refresh_from_db()
    assert w.laser.open_to_all_members is False


def test_the_later_expiring_purpose_wins_when_both_are_met():
    w, service, booking = _gated()
    soon, later = timezone.now() + timedelta(days=5), timezone.now() + timedelta(days=50)
    CertificationGrant.objects.create(certification_type=service, membership=w.membership, expires_at=soon)
    CertificationGrant.objects.create(certification_type=booking, membership=w.membership, expires_at=later)
    run()
    assert MachineAccessGrant.objects.get(member=w.member).expires_at == later


def test_a_never_expiring_purpose_beats_an_expiring_one():
    w, service, booking = _gated()
    CertificationGrant.objects.create(certification_type=service, membership=w.membership,
                                      expires_at=timezone.now() + timedelta(days=5))
    CertificationGrant.objects.create(certification_type=booking, membership=w.membership)
    run()
    assert MachineAccessGrant.objects.get(member=w.member).expires_at is None


def test_one_type_required_for_both_purposes_is_enough_alone():
    w = world()
    w.space.enabled_features = sorted({*(w.space.enabled_features or []), "machines.certifications"})
    w.space.save(update_fields=["enabled_features"])
    both = CertificationType.objects.create(makerspace=w.space, machine_type=w.kind, name="Laser induction",
                                            is_required_for_service=True, is_required_for_booking=True)
    CertificationGrant.objects.create(certification_type=both, membership=w.membership)
    run()
    run()
    assert MachineAccessGrant.objects.filter(member=w.member, machine_type=w.kind).count() == 1
