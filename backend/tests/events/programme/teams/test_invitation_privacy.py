import pytest
from apps.events.hackathons.admission_errors import ProgrammeError
from apps.events.hackathons.team_invitations import invite, accept
from apps.events.hackathons.team_workflow import create
from tests.events.programme.admission.test_support import world, submitted, cmd

pytestmark = pytest.mark.django_db


def make_team(world):
    app = submitted(world)
    app.state = "confirmed"
    app.save()
    return create(event_id=world.event.pk, actor=world.owner, data=cmd(0, name="Builders"))


def test_invalid_token_does_not_reveal_team_version_before_refusal(world):
    team = make_team(world)
    with pytest.raises(ProgrammeError) as exc:
        accept(event_id=world.event.pk, team_id=team.pk, actor=world.other,
               data=cmd(999, token="0" * 64))
    assert exc.value.detail["code"] == "not_found"
    assert "current_version" not in exc.value.detail


def test_rotate_revokes_old_invitation_and_no_raw_token_is_stored(world):
    team = make_team(world)
    first, token = invite(event_id=world.event.pk, team_id=team.pk, actor=world.owner, data=cmd(team.version, rotate=False))
    team.refresh_from_db()
    second, other = invite(event_id=world.event.pk, team_id=team.pk, actor=world.owner, data=cmd(team.version, rotate=True))
    first.refresh_from_db()
    assert first.revoked_at is not None and token != other
    assert token != first.token_digest and not hasattr(first, "token")


def test_bound_invitation_requires_verified_account_email_not_contact_fallback(world):
    team = make_team(world)
    row, token = invite(event_id=world.event.pk, team_id=team.pk, actor=world.owner,
                        data=cmd(team.version, email=world.other.email))
    team.refresh_from_db()
    with pytest.raises(ProgrammeError) as exc:
        accept(event_id=world.event.pk, team_id=team.pk, actor=world.other,
               data=cmd(team.version, token=token))
    assert exc.value.status_code == 404
    row.refresh_from_db()
    assert row.redeemed_at is None
