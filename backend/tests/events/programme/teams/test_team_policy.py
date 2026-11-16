from datetime import timedelta
from types import SimpleNamespace
import pytest
from django.utils import timezone
from apps.events.hackathons.admission_errors import ProgrammeError
from apps.events.hackathons.admission_cohorts import roster_hash
from apps.events.hackathons.team_workflow import normalized_name, require_forming
from apps.events.hackathons.team_invitations import digest, invitation_token


def test_name_normalization_prevents_unicode_and_whitespace_duplicates():
    assert normalized_name("  Ｍaker   Crew  ") == ("Maker Crew", "maker crew")
    with pytest.raises(ProgrammeError):
        normalized_name("Team\x00name")


def test_roster_seal_is_order_independent_and_member_application_bound():
    members = [SimpleNamespace(member_id=2, application_id=5), SimpleNamespace(member_id=1, application_id=4)]
    assert roster_hash(members) == roster_hash(list(reversed(members)))
    assert roster_hash(members) != roster_hash([SimpleNamespace(member_id=2, application_id=4)])


def test_pending_invitation_has_no_raw_credential_in_digest(settings):
    settings.SECRET_KEY = "fixture-only"
    token = invitation_token(21, 17, "33333333-3333-4333-8333-333333333333")
    assert len(token) == 64
    assert token != digest(token, purpose="token")
    assert digest("member@example.test", purpose="email") != digest("member@example.test", purpose="token")
    assert token == invitation_token(21, 17, "33333333-3333-4333-8333-333333333333")


@pytest.mark.parametrize("state", ["locked", "disbanded"])
def test_closed_team_cannot_change_roster(state):
    with pytest.raises(ProgrammeError) as exc:
        require_forming(SimpleNamespace(team_lock_at=None), SimpleNamespace(state=state))
    assert exc.value.detail["code"] == "team_locked"


def test_roster_deadline_enforced_even_before_sweeper():
    with pytest.raises(ProgrammeError):
        require_forming(SimpleNamespace(team_lock_at=timezone.now() - timedelta(seconds=1)), SimpleNamespace(state="forming"))
