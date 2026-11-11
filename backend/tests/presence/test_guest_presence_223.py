"""Decision 223 (j) and the guest arm of the guards: waiver for every on-site non-member (gap G2),
staff check-in of a pass holder, the desk waiver stamp, and `require_member_or_guest`."""
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.makerspaces import guest_pass_issue
from apps.makerspaces.guest_pass_policy import GuestPassError
from apps.makerspaces.models import GuestPassPolicy, MakerspaceWaiver
from apps.presence import services
from apps.presence.guard import MemberPresenceRequired, PresenceRequired, WaiverAcceptanceRequired
from apps.presence.guest_guard import require_borrowing, require_member_or_guest
from apps.presence.policy import PresenceError
from tests.makerspaces.l4_helpers import features_on
from tests.makerspaces.test_guest_passes import _space, _sponsor
from tests.makerspaces.test_membership_j1 import manager, user
from .fence_helpers import INSIDE, fence

pytestmark = pytest.mark.django_db(transaction=True)


def _setup(slug, *, waiver=True, **policy):
    makerspace = fence(_space(slug))
    if policy:
        GuestPassPolicy.objects.filter(makerspace=makerspace).update(**policy)
    if waiver:
        MakerspaceWaiver.objects.create(makerspace=makerspace, version="v1", body="Sign here", is_active=True)
    return makerspace


def _pass(makerspace, guest, **kwargs):
    row, _ = guest_pass_issue.issue_staff_pass(manager(makerspace, "issuer"), makerspace, guest, **kwargs)
    return row


def test_account_only_guest_self_check_in_needs_the_waiver_g2():
    makerspace = _setup("g2-waiver")
    guest = user("g2-guest")
    with pytest.raises(PresenceError) as refused:
        services.start_session(guest, makerspace, 60, **INSIDE)
    assert refused.value.detail["code"] == "waiver_acceptance_required"


def test_guest_self_check_in_passes_once_the_pass_carries_the_waiver():
    makerspace = _setup("g2-pass")
    guest = user("g2-stamped")
    row = _pass(makerspace, guest)
    from apps.makerspaces.guest_pass_lifecycle import stamp_waiver
    stamp_waiver(guest, row)
    session = services.start_session(guest, makerspace, 60, **INSIDE)
    assert session.status == "guest"


def test_waiver_not_required_when_the_space_turns_it_off_or_publishes_none():
    off = _setup("g2-off", waiver=True, waiver_required_on_site=False)
    assert services.start_session(user("g2-off-guest"), off, 60, **INSIDE).status == "guest"
    none = _setup("g2-none", waiver=False)
    assert services.start_session(user("g2-none-guest"), none, 60, **INSIDE).status == "guest"


def test_staff_may_check_in_only_a_pass_holder_and_can_stamp_the_waiver_at_the_desk():
    makerspace = _setup("desk-checkin")
    staff, stranger, guest = manager(makerspace), user("stranger"), user("desk-guest")
    with pytest.raises(PresenceError) as no_pass:
        services.staff_check_in(staff, stranger, makerspace, 60)
    assert no_pass.value.detail["code"] == "account_not_in_space"
    row = _pass(makerspace, guest)
    with pytest.raises(PresenceError) as unsigned:
        services.staff_check_in(staff, guest, makerspace, 60)
    assert unsigned.value.detail["code"] == "waiver_acceptance_required"
    session = services.staff_check_in(staff, guest, makerspace, 60, waiver_accepted_at_desk=True)
    row.refresh_from_db()
    assert session.status == "guest" and row.accepted_waiver_id is not None


def test_expired_pass_no_longer_lets_staff_check_the_guest_in():
    makerspace = _setup("desk-expired", waiver=False)
    guest = user("expired-guest")
    row = _pass(makerspace, guest)
    type(row).objects.filter(pk=row.pk).update(valid_until=timezone.now() - timedelta(minutes=1),
                                               valid_from=timezone.now() - timedelta(hours=2))
    with pytest.raises(PresenceError):
        services.staff_check_in(manager(makerspace), guest, makerspace, 60)


def test_guard_admits_a_pass_holder_only_with_session_and_waiver():
    makerspace = _setup("guard-guest")
    guest = user("guard-guest")
    row = _pass(makerspace, guest)
    with pytest.raises(WaiverAcceptanceRequired):
        require_member_or_guest(guest, makerspace)
    from apps.makerspaces.guest_pass_lifecycle import stamp_waiver
    stamp_waiver(guest, row)
    with pytest.raises(PresenceRequired):
        require_member_or_guest(guest, makerspace)
    services.start_session(guest, makerspace, 60, **INSIDE)
    admitted = require_member_or_guest(guest, makerspace)
    assert admitted.membership is None and admitted.guest_pass.pk == row.pk


def test_planning_needs_neither_presence_nor_waiver_but_still_a_live_pass():
    makerspace = _setup("guard-planning")
    guest, stranger = user("plan-guest"), user("plan-stranger")
    row = _pass(makerspace, guest)
    assert require_member_or_guest(guest, makerspace, planning=True, borrow=True).guest_pass.pk == row.pk
    with pytest.raises(MemberPresenceRequired):
        require_member_or_guest(stranger, makerspace, planning=True)


def test_borrowing_mode_none_refuses_with_a_stable_code_and_on_site_refuses_take_home():
    makerspace = _setup("guard-borrow", guest_borrowing_mode="none")
    guest = user("borrow-guest")
    row = _pass(makerspace, guest)
    with pytest.raises(GuestPassError) as refused:
        require_borrowing(row)
    assert refused.value.error_code == "guest_pass_no_borrow"
    row.entitlements = {**row.entitlements, "borrow": "on_site"}
    with pytest.raises(GuestPassError) as on_site:
        require_borrowing(row, take_home=True)
    assert on_site.value.error_code == "guest_pass_on_site_only"
    assert require_borrowing(row).on_site_only is True


def test_member_path_is_unchanged_and_ignores_the_pass_arm():
    makerspace = _setup("guard-member", waiver=False)
    member = _sponsor(makerspace, "guard-member")
    with pytest.raises(PresenceRequired):
        require_member_or_guest(member, makerspace)
    services.start_session(member, makerspace, 60, **INSIDE)
    assert require_member_or_guest(member, makerspace).guest_pass is None
