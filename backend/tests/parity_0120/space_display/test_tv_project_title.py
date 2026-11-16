"""The anonymous /now projection reads the ACCOUNT profile's projects (decisions 303/304), not legacy rows."""
import pytest

from apps.makerspaces.models_account_profile import AccountProject
from apps.presence.display import tv_payload

pytestmark = pytest.mark.django_db


def _working(lane, *, public=True, show_projects=True, project_public=True, visible=True):
    user = lane.person("builder")
    profile = lane.profile(user, public=public, show_projects=show_projects, is_visible=visible)
    project = AccountProject.objects.create(profile=profile, title="Rover", public_visible=project_public)
    lane.check_in(user, status="working", project_id=project.pk)  # no MemberProfile / MemberProject exists
    return user


def test_new_account_project_title_shows_for_open_web_profile(lane):
    _working(lane)
    assert tv_payload(lane.space, use_cache=False)[0]["project_title"] == "Rover"


@pytest.mark.parametrize("kwargs", [
    {"public": False}, {"show_projects": False}, {"project_public": False}, {"visible": False},
])
def test_title_withheld_unless_every_gate_is_open(lane, kwargs):
    _working(lane, **kwargs)
    assert "project_title" not in tv_payload(lane.space, use_cache=False)[0]


def test_session_refuses_someone_elses_project(lane):
    owner, other = lane.person("owner"), lane.person("other")
    project = AccountProject.objects.create(profile=lane.profile(owner), title="Mine")
    from apps.presence.policy import PresenceError
    with pytest.raises(PresenceError):
        lane.check_in(other, status="working", project_id=project.pk)
