"""Tinkerspace applications, review stages, crew and check-in lists (release 2 L21a, #134 walkthrough).

Turns the L21a switches on and seeds, through the real services: an open-studio residency
that takes applications (solo, batch review) with two review stages and a two-person panel
on the first; and, on the L6 build night, a crew with free places (one marshal, one on the
door, the crew sign-up link open) plus a T-shirt list for add-on buyers and a pizza list
after entry. Attendance confirmation is left for staff to send from the walkthrough.
"""

from datetime import timedelta
from uuid import uuid4

from django.utils import timezone

from apps.events import checkin_lists
from apps.events.contributions import crew_workflow
from apps.events.hackathons import admission_stages
from apps.events.hackathons.admission_models import HackathonConfig
from apps.events.models import EventAddon, EventParticipationSettings

FEATURES = ("events.applications", "events.application_stages", "events.attendance_confirmation",
            "events.crew", "events.checkin_lists")
STAGES = (("Screening", 1, [{"key": "motivation", "label": "Motivation"}, {"key": "portfolio", "label": "Portfolio"}]),
          ("Studio interview", 2, [{"key": "fit", "label": "Fit with the studio"}]))


def _command(version=0, **values):
    return {"operation_id": uuid4(), "expected_version": version, **values}


def seed_participation(space, manager, members, build_night):
    from apps.events.services_event_details import create_event
    from apps.events.services_lifecycle import publish
    space.enabled_features = sorted(set(space.enabled_features or []) | set(FEATURES))
    space.save(update_fields=["enabled_features"])
    people = list(members.values())
    starts = (timezone.now() + timedelta(days=30)).replace(hour=10, minute=0, second=0, microsecond=0)
    residency = create_event(makerspace=space, actor=manager, title="Open studio residency",
                             description="Four weekends in the studio. Apply with a short portfolio.",
                             starts_at=starts, ends_at=starts + timedelta(days=1), location="Studio", capacity=6,
                             is_public=True)
    publish(residency, actor=manager)
    HackathonConfig.objects.create(event=residency, enabled=True, team_mode="solo", review_mode="batch")
    for name, target, criteria in STAGES:
        stage = admission_stages.create(event_id=residency.pk, actor=manager, data=_command(
            name=name, reviews_per_application=target, criteria=criteria, blind=name == "Screening"))
    first = admission_stages.stages_for(residency.pk).first()
    admission_stages.set_panel(event_id=residency.pk, stage_id=first.pk, actor=manager,
                               data=_command(first.version, reviewer_ids=[people[0].pk, people[1].pk]))
    EventParticipationSettings.objects.update_or_create(event=build_night, defaults={
        "makerspace": space, "crew_signup_open": True, "crew_public_section": True})
    crew_workflow.add(build_night, actor=manager, member=people[2], crew_role="Arena marshal")
    crew_workflow.add(build_night, actor=manager, member=people[3], crew_role="Door")
    shirt = EventAddon.objects.filter(event=build_night).first()
    if shirt is not None:
        checkin_lists.create(build_night, actor=manager, data={"name": "Arena T-shirts", "kind": "swag",
                                                               "addon_id": shirt.pk})
    checkin_lists.create(build_night, actor=manager, data={"name": "Pizza", "kind": "meal", "after_entry": True})
    return residency, stage
