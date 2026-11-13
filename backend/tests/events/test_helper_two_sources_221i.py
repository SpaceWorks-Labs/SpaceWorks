"""Decision 221(i), audit item B6: an inviter holding two separate limited sources.

The invite limit needs the inviter's own `manage_team` source to cover the scope AND a source
covering each helper permission, so a separate, wider `judge` source cannot lift a
track-limited `manage_team`, and two disjoint track limits never combine.
"""
import pytest

from apps.events import event_authority, services_staff_grants as services
from apps.events.contributions.models_roles import EventGrantEntitlement, EventRoleAssignment
from tests.events.test_decision15_coorganizer_journeys import REFUSED, person, world  # noqa: F401
from tests.events.test_helper_window_221i import limited

pytestmark = pytest.mark.django_db


def second_source(w, user, permissions, track_ids):
    """A separate live entitlement (a programme role source) on the same grant."""
    role = EventRoleAssignment.objects.create(
        event=w.event, makerspace=w.space, member=user, role="judge", state="approved", approved_by=w.manager)
    grant = user.event_staff_grants.get(event=w.event, revoked_at__isnull=True)
    return EventGrantEntitlement.objects.create(
        event=w.event, makerspace=w.space, grant=grant, source_kind="role", role_assignment=role,
        permissions=permissions, track_ids=track_ids, created_by=w.manager)


def test_a_wider_judge_source_does_not_escape_a_track_limited_manage_team():
    w = world("w221i-two")
    inviter = limited(w, track_ids=[7])
    second_source(w, inviter, ["judge"], [])  # event-wide judge, separate from the limited manage_team
    invite, token = services.create_invite(w.event, actor=inviter, permissions=["judge"])
    assert invite.track_ids == [7]  # inherits the manage_team limit, not the wider judge source
    with pytest.raises(REFUSED):
        services.create_invite(w.event, actor=inviter, permissions=["judge"], track_ids=[8])
    helper = person("two-source-helper")
    services.redeem_invite(token, actor=helper)
    assert event_authority.can(helper, w.event, "judge", track_id=7)
    assert not event_authority.can(helper, w.event, "judge")


def test_two_disjoint_limited_sources_cover_no_invite():
    w = world("w221i-disjoint")
    inviter = limited(w, track_ids=[7])
    second_source(w, inviter, ["judge"], [8])
    for tracks in ([7], [8], [7, 8]):
        with pytest.raises(REFUSED):
            services.create_invite(w.event, actor=inviter, permissions=["judge"], track_ids=tracks)
