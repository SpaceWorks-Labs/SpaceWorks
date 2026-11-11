"""Decision 223 (d): a guest-pass holder's machine mode in sessions and job intake."""
import pytest

from apps.machines import guest_access
from apps.machines.guest_access import GuestMachineRefused
from apps.machines.models import CertificationType, GuestCertificationGrant, Machine, MachineType
from apps.machines.sessions_rules import SessionRefused, require_can_start
from apps.makerspaces import guest_pass_issue
from apps.makerspaces.models import GuestPassPolicy
from tests.makerspaces.test_guest_passes import _space
from tests.makerspaces.test_membership_j1 import manager, user

pytestmark = pytest.mark.django_db(transaction=True)


def _machine(makerspace, slug):
    machine_type = MachineType.objects.create(makerspace=makerspace, name=f"Laser {slug}", slug=f"laser-{slug}")
    return Machine.objects.create(makerspace=makerspace, machine_type=machine_type, name=f"Cutter {slug}")


def _guest(makerspace, name, mode):
    GuestPassPolicy.objects.filter(makerspace=makerspace).update(guest_machine_mode=mode,
                                                                 waiver_required_on_site=False)
    guest = user(name)
    row, _ = guest_pass_issue.issue_staff_pass(manager(makerspace, f"{name}-staff"), makerspace, guest)
    return guest, row


def test_mode_none_refuses_with_guest_pass_no_machines():
    makerspace = _space("gm-none")
    machine = _machine(makerspace, "none")
    guest, row = _guest(makerspace, "gm-none-guest", "none")
    with pytest.raises(GuestMachineRefused) as refused:
        guest_access.require_guest_machine(row, guest, makerspace, machine=machine)
    assert refused.value.code == "guest_pass_no_machines" and refused.value.status_code == 403


def test_supervised_mode_refuses_a_self_service_session_and_a_job():
    makerspace = _space("gm-supervised")
    machine = _machine(makerspace, "sup")
    guest, row = _guest(makerspace, "gm-sup-guest", "supervised")
    with pytest.raises(GuestMachineRefused) as session:
        guest_access.require_guest_machine(row, guest, makerspace, machine=machine)
    assert session.value.code == "guest_pass_supervised_only"
    with pytest.raises(GuestMachineRefused) as job:
        guest_access.require_guest_machine(row, guest, makerspace, machine_type=machine.machine_type, surface="job")
    assert job.value.code == "guest_pass_supervised_only"


def test_after_induction_cert_needs_a_guest_certification_for_the_machine_type():
    makerspace = _space("gm-cert")
    machine = _machine(makerspace, "cert")
    guest, row = _guest(makerspace, "gm-cert-guest", "after_induction_cert")
    with pytest.raises(GuestMachineRefused) as refused:
        guest_access.require_guest_machine(row, guest, makerspace, machine=machine)
    assert refused.value.code == "guest_pass_certification_required"
    cert = CertificationType.objects.create(makerspace=makerspace, machine_type=machine.machine_type,
                                            name="Laser induction", is_active=True)
    GuestCertificationGrant.objects.create(makerspace=makerspace, certification_type=cert, user=guest,
                                           granted_by=manager(makerspace))
    guest_access.require_guest_machine(row, guest, makerspace, machine=machine)  # no raise


def test_session_start_runs_the_machine_mode_for_a_pass_holder():
    makerspace = _space("gm-session")
    machine = _machine(makerspace, "session")
    guest, _row = _guest(makerspace, "gm-session-guest", "none")
    from apps.presence import services
    from tests.presence.fence_helpers import INSIDE, fence
    fence(makerspace)
    services.start_session(guest, makerspace, 60, **INSIDE)
    with pytest.raises((GuestMachineRefused, SessionRefused)) as refused:
        require_can_start(machine, guest)
    assert refused.value.code == "guest_pass_no_machines"


def test_a_member_is_unaffected_by_the_guest_machine_gate():
    makerspace = _space("gm-member")
    machine = _machine(makerspace, "member")
    from tests.makerspaces.test_guest_passes import _sponsor
    member = _sponsor(makerspace, "gm-member")
    from apps.presence import services
    from tests.presence.fence_helpers import INSIDE, fence
    fence(makerspace)
    services.start_session(member, makerspace, 60, **INSIDE)
    require_can_start(machine, member)  # certifications are off, so nothing refuses a plain member
