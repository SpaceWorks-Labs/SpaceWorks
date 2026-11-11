"""Real PostgreSQL parent locking; G must run with the A model migration installed."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from django.db import close_old_connections
import pytest
from apps.events.hackathons.admission_errors import ProgrammeError
from apps.events.hackathons.team_invitations import invite, accept
from apps.events.hackathons.team_workflow import create
from tests.events.ticketing_helpers import account
from tests.events.programme.admission.test_support import world, submitted, cmd

pytestmark = pytest.mark.django_db(transaction=True)


def test_two_invite_accepts_cannot_take_the_same_last_team_place(world):
    world.config.team_max = 2
    world.config.save()
    third = account("a-third")
    for actor in (world.owner, world.other, third):
        app = submitted(world, actor)
        app.state = "confirmed"
        app.save()
    team = create(event_id=world.event.pk, actor=world.owner, data=cmd(0, name="Last slot"))
    _, first = invite(event_id=world.event.pk, team_id=team.pk, actor=world.owner, data=cmd(team.version))
    team.refresh_from_db()
    _, second = invite(event_id=world.event.pk, team_id=team.pk, actor=world.owner, data=cmd(team.version))
    team.refresh_from_db()
    barrier = Barrier(2)
    def respond(actor, token):
        close_old_connections()
        try:
            barrier.wait(timeout=10)
            try:
                accept(event_id=world.event.pk, team_id=team.pk, actor=actor,
                       data=cmd(team.version, token=token))
                return "joined"
            except ProgrammeError as exc:
                return str(exc.detail["code"])
        finally:
            close_old_connections()
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(respond, world.other, first), pool.submit(respond, third, second)]
        outcomes = [f.result(timeout=20) for f in futures]
    assert outcomes.count("joined") == 1
    assert set(outcomes) <= {"joined", "stale_version", "capacity_full"}
    assert team.memberships.filter(state="active").count() == 2
