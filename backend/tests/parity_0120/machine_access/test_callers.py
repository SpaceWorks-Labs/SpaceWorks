"""Every caller asks the one function; certifications no longer gate anything (decision 319)."""
import pytest
from rest_framework.exceptions import PermissionDenied

from apps.bookings.models import Booking
from apps.machines import access_grants as ag
from apps.machines.models import CertificationGrant, CertificationType, MachineAccessGrant
from apps.machines.sessions_rules import refusal
from tests.machines.certification_helpers import _bookable, _book, _submit
from tests.machines.session_helpers import check_in
from tests.parity_0120.machine_access.helpers import world
from tests.rbac_f6_helpers import community_member

pytestmark = pytest.mark.django_db


def _member_in_space(w):
    membership = community_member(w.space, "operator")
    check_in(w.space, membership)
    return membership.user


def test_sessions_refuse_without_a_grant_then_allow_with_one():
    w = world()
    user = _member_in_space(w)
    found = refusal(w.laser, user)
    assert found["code"] == "no_machine_access"
    MachineAccessGrant.objects.create(makerspace=w.space, member=user, machine_type=w.kind)
    assert refusal(w.laser, user) is None


def test_session_refusal_never_mentions_certifications():
    w = world()
    user = _member_in_space(w)
    assert "certification" not in str(refusal(w.laser, user))


def test_a_certification_record_no_longer_gates_or_grants_anything():
    w = world()
    user = _member_in_space(w)
    row = CertificationType.objects.create(makerspace=w.space, machine_type=w.kind, name="Laser induction",
                                           is_required_for_service=True, is_required_for_booking=True)
    CertificationGrant.objects.create(certification_type=row, membership=w.membership)
    assert refusal(w.laser, user)["code"] == "no_machine_access"
    assert ag.can_use(w.member, w.laser) == (False, "no_machine_access")


def test_job_requests_need_a_type_grant():
    w = world()
    with pytest.raises(PermissionDenied) as caught:
        _submit(w.laser, w.member)
    assert caught.value.detail["code"] == "no_machine_access"
    MachineAccessGrant.objects.create(makerspace=w.space, member=w.member, machine_type=w.kind)
    assert _submit(w.laser, w.member).pk is not None


def test_machine_bookings_need_access_to_the_linked_machine_or_type():
    w = world()
    space_row = _bookable(w.space, w.kind)
    with pytest.raises(PermissionDenied) as caught:
        _book(space_row, w.member)
    assert caught.value.detail["code"] == "no_machine_access"
    assert not Booking.objects.exists()
    MachineAccessGrant.objects.create(makerspace=w.space, member=w.member, machine_type=w.kind)
    assert _book(space_row, w.member).status == Booking.Status.CONFIRMED


def test_a_room_with_no_machine_type_is_never_gated():
    w = world()
    assert _book(_bookable(w.space, None), w.member).pk is not None


def test_guest_after_induction_mode_follows_a_grant_not_a_certification(monkeypatch):
    from apps.machines.guest_access import GuestMachineRefused, require_guest_machine
    w = world()
    monkeypatch.setattr("apps.machines.guest_access.pass_entitlements",
                        lambda guest_pass: type("E", (), {"machines": "after_induction_cert"})())
    with pytest.raises(GuestMachineRefused) as caught:
        require_guest_machine(object(), w.member, w.space, machine=w.laser)
    assert caught.value.code == "guest_pass_machine_access_required"
    MachineAccessGrant.objects.create(makerspace=w.space, member=w.member, machine=w.laser)
    require_guest_machine(object(), w.member, w.space, machine=w.laser)


def test_adapter_reason_vocabulary_replaced_the_certification_code():
    from apps.devices.adapters.caps.access_authorize import REASONS
    from apps.devices.services_adapter_access import normalise_reason
    assert "certification_required" not in REASONS
    assert {"no_machine_access", "machine_access_expired"} <= set(REASONS)
    assert normalise_reason("no_machine_access") == "no_machine_access"
    assert normalise_reason("machine_access_expired") == "machine_access_expired"
