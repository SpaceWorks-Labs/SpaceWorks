"""Whole-cohort admission/reopening uses the real registration and money seams."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from django.db import close_old_connections

from apps.events import services
from apps.events.credentials.models import EventRegistrationCredential
from apps.events.hackathons import team_workflow, team_invitations, team_lifecycle
from apps.events.hackathons.admission_cohorts import reopen_locked
from apps.events.hackathons.admission_errors import ProgrammeError
from apps.events.hackathons.admission_models import HackathonApplicationAnswerRevision
from apps.events.hackathons.admission_rsvp import rsvp
from apps.events.hackathons.admission_transactions import command as admission_command
from apps.events.models import EventRegistration
from apps.payments.models import Payment
from tests.events.ticketing_helpers import account
from .g2a_support import canonical_world, apply, command

pytestmark = pytest.mark.django_db(transaction=True)


def cohort(world, *, capacity=2):
    world.event.capacity = capacity
    world.event.save(update_fields=["capacity"])
    world.config.team_mode, world.config.team_max = "team_together", 2
    world.config.save(update_fields=["team_mode", "team_max"])
    first, second = apply(world), apply(world, world.other)
    team = team_workflow.create(event_id=world.event.pk, actor=world.owner, data=command(0, name="Circuit crew"))
    _, token = team_invitations.invite(event_id=world.event.pk, team_id=team.pk, actor=world.owner,
                                      data=command(team.version))
    team.refresh_from_db()
    team_invitations.accept(event_id=world.event.pk, team_id=team.pk, actor=world.other,
                            data=command(team.version, token=token))
    team.refresh_from_db()
    team_lifecycle.lock(event_id=world.event.pk, team_id=team.pk, actor=world.owner, data=command(team.version))
    first.refresh_from_db()
    second.refresh_from_db()
    return team, first, second


def test_all_rsvps_confirm_together_and_legacy_cancel_ends_every_member(canonical_world):
    w = canonical_world
    _, first, second = cohort(w)
    rsvp(event_id=w.event.pk, actor=w.owner, data=command(first.version, decision="accept"))
    assert not Payment.objects.filter(makerspace=w.space).exists()
    assert not EventRegistration.objects.filter(event=w.event, status="registered").exists()
    rsvp(event_id=w.event.pk, actor=w.other, data=command(second.version, decision="accept"))
    assert EventRegistration.objects.filter(event=w.event, status="registered").count() == 2
    assert Payment.objects.filter(makerspace=w.space, subject_type="event_registration").count() == 2
    services.cancel_registration(first.registration, actor=w.manager)
    first.refresh_from_db()
    second.refresh_from_db()
    assert first.state == second.state == "withdrawn"
    assert EventRegistration.objects.filter(event=w.event, status="cancelled").count() == 2
    assert not EventRegistrationCredential.objects.filter(registration__event=w.event, revoked_at=None).exists()
    assert Payment.objects.filter(makerspace=w.space, subject_type="event_registration").count() == 2


def test_cohort_final_rsvp_rolls_back_if_hard_seats_cannot_fit_whole_group(canonical_world):
    w = canonical_world
    _, first, second = cohort(w, capacity=1)
    rsvp(event_id=w.event.pk, actor=w.owner, data=command(first.version, decision="accept"))
    with pytest.raises(ProgrammeError) as error:
        rsvp(event_id=w.event.pk, actor=w.other, data=command(second.version, decision="accept"))
    assert error.value.detail["code"] == "capacity_full"
    second.refresh_from_db()
    assert second.state == "offered" and second.rsvp_accepted_at is None
    assert not EventRegistration.objects.filter(event=w.event, status="registered").exists()
    assert not Payment.objects.filter(makerspace=w.space).exists()


def test_staff_reopen_archives_answers_and_retains_registration_and_debt(canonical_world):
    w = canonical_world
    team, first, second = cohort(w)
    rsvp(event_id=w.event.pk, actor=w.owner, data=command(first.version, decision="accept"))
    rsvp(event_id=w.event.pk, actor=w.other, data=command(second.version, decision="accept"))
    ids = {first.registration_id, second.registration_id}
    payments = set(Payment.objects.filter(makerspace=w.space).values_list("pk", flat=True))
    first.refresh_from_db()
    with admission_command(event_id=w.event.pk, actor=w.manager, data=command(first.version),
                           action="test.staff_cohort_reopen", permission="review_applications") as ctx:
        reopen_locked(ctx, first.cohort)
        ctx.finish("cohort", first.cohort_id)
    assert set(EventRegistration.objects.filter(event=w.event).values_list("pk", flat=True)) == ids
    assert set(Payment.objects.filter(makerspace=w.space).values_list("pk", flat=True)) == payments
    assert HackathonApplicationAnswerRevision.objects.filter(application__event=w.event).count() == 2
    assert not EventRegistrationCredential.objects.filter(registration__event=w.event, revoked_at=None).exists()


def test_two_real_team_accepts_cannot_take_the_last_slot_twice(canonical_world):
    w = canonical_world
    w.event.capacity = 0
    w.event.save(update_fields=["capacity"])
    w.config.offer_capacity, w.config.team_max = 3, 2
    w.config.save(update_fields=["offer_capacity", "team_max"])
    third = account("g2a-third")
    for member in (w.owner, w.other, third):
        app = apply(w, member)
        rsvp(event_id=w.event.pk, actor=member, data=command(app.version, decision="accept"))
    team = team_workflow.create(event_id=w.event.pk, actor=w.owner, data=command(0, name="Last slot"))
    _, first = team_invitations.invite(event_id=w.event.pk, team_id=team.pk, actor=w.owner, data=command(team.version))
    team.refresh_from_db()
    _, second = team_invitations.invite(event_id=w.event.pk, team_id=team.pk, actor=w.owner, data=command(team.version))
    team.refresh_from_db()
    barrier = Barrier(2)

    def accept(member, token):
        close_old_connections()
        try:
            barrier.wait(8)
            try:
                team_invitations.accept(event_id=w.event.pk, team_id=team.pk, actor=member,
                                        data=command(team.version, token=token))
                return "joined"
            except ProgrammeError as exc:
                return exc.detail["code"]
        finally:
            close_old_connections()
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(accept, w.other, first), pool.submit(accept, third, second)]
        results = [future.result(timeout=20) for future in futures]
    assert results.count("joined") == 1
    assert set(results) <= {"joined", "stale_version", "capacity_full"}
    assert team.memberships.filter(state="active").count() == 2


def test_series_schedule_edit_cancels_old_admission_without_copying_people(canonical_world):
    from datetime import time, timedelta
    from django.utils import timezone
    from apps.events import services_series
    from apps.events.hackathons.admission_models import HackathonApplication, HackathonConfig, HackathonCocRevision
    w = canonical_world
    series, occurrences = services_series.create_series(makerspace=w.space, actor=w.manager, title="Programme series",
        recurrence_timezone="UTC", dtstart_local_date=(timezone.now() + timedelta(days=1)).date(),
        dtstart_local_time=time(10), recurrence_rule="FREQ=DAILY;COUNT=2", duration_minutes=60,
        registration_audience="accounts", capacity=2, is_public=True)
    services_series.publish_series(series, actor=w.manager)
    w.event = occurrences[0]
    w.event.refresh_from_db()
    w.config = HackathonConfig.objects.create(event=w.event, enabled=True, review_mode="auto",
        application_form={"schema_version": 2, "form_id": "application", "revision": 1, "questions": []})
    HackathonCocRevision.objects.create(event=w.event, revision=1, body="Be considerate.")
    app = apply(w)
    _, created, _ = services_series.update_series(series, actor=w.manager, effective_from=timezone.now(),
                                                  dtstart_local_time=time(11))
    app.refresh_from_db()
    w.event.refresh_from_db()
    assert w.event.status == "cancelled" and app.state == "withdrawn" and app.registration.status == "cancelled"
    assert app.answer_locked_at is not None
    assert created and not HackathonApplication.objects.filter(event_id__in=[event.pk for event in created]).exists()
