"""EV-30: the staff shift view names the volunteer; the member's own signup view never carries it."""
import pytest

from apps.events.contributions import projections
from apps.events.contributions.models import EventShiftSignup
from tests.events.programme.contributions.helpers import setup_shift

pytestmark = pytest.mark.django_db


def test_staff_signup_projection_has_member_name_and_member_projection_does_not(settings):
    space, event, _, shift, users, roles, _adapter = setup_shift(settings)
    users[0].display_name = "Grace Hopper"
    users[0].save(update_fields=["display_name"])
    signup = EventShiftSignup.objects.create(event=event, makerspace=space, shift=shift,
                                             assignment=roles[0], member=users[0], state="approved")
    staff_view = projections.signup(signup, owner=False)
    assert staff_view["member_name"] == "Grace Hopper"
    assert "member_name" not in projections.signup(signup, owner=True)
    listed = projections.admin_shift(shift, users[1])["signups"]
    assert [row["member_name"] for row in listed] == ["Grace Hopper"]


def test_member_name_falls_back_to_username(settings):
    space, event, _, shift, users, roles, _adapter = setup_shift(settings)
    users[0].display_name = ""
    users[0].save(update_fields=["display_name"])
    signup = EventShiftSignup.objects.create(event=event, makerspace=space, shift=shift,
                                             assignment=roles[0], member=users[0], state="approved")
    assert projections.signup(signup, owner=False)["member_name"] == users[0].username
