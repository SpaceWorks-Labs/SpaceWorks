"""Checked-in person sessions for the G2 public/member route proofs."""
from apps.machines.models import MachineType, ServiceQueue
from tests.machines.route_support_cx11b_g2 import personal, world
from tests.machines.session_helpers import check_in
from tests.rbac_f6_helpers import community_member
from tests.accounts.account_factories import make_membership


def member_world(native):
    w = world(native)
    membership = community_member(w.space, "g2-member")
    w.member = membership.user
    check_in(w.space, membership)
    w.client = personal(w.member, w.space, native)
    # A same-space non-owner as well as a foreign person is required for own rows.
    w.bystander = community_member(w.space, "g2-bystander").user
    w.same_space = personal(w.bystander, w.space, native)
    make_membership(w.outsider, w.other)
    w.foreign = personal(w.outsider, w.other, native)
    MachineType.objects.filter(pk=w.machine_type.pk).update(
        slug="laser_cutter", capability_config={"metering_unit": "minutes", "requires_booking": False})
    w.machine_type.refresh_from_db()
    w.machine.open_to_all_members = True
    w.machine.is_public = True
    w.machine.save(update_fields=["open_to_all_members", "is_public"])
    w.kind, w.staff = w.machine_type, w.actor
    w.queue = ServiceQueue.objects.create(makerspace=w.space, machine_type=w.kind, name="Retained job queue")
    return w
