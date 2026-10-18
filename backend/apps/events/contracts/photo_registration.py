"""C/D/pages -> E live selected-profile eligibility and public card values."""

from urllib.parse import urlsplit

from django.http import Http404

from apps.events.contributions.models_roles import EventRoleAssignment
from apps.events.hackathons.admission_models import HackathonApplication
from apps.events.hackathons.team_models import HackathonTeamMember
from apps.events.models_event import Event
from apps.events.profile_photos.projection import project_public
from apps.events.website_visibility import visible_page


def application_subject(*, event_id, member_id):
    return HackathonApplication.objects.filter(event_id=event_id, member_id=member_id,
        state__in=("draft", "submitted", "offered", "waitlisted", "confirmed")).exists()


def role_subject(*, event_id, member_id):
    return EventRoleAssignment.objects.filter(event_id=event_id, member_id=member_id, imported_inert=False,
        state__in=("draft", "proposed", "applied", "approved", "completed")).exists()


def role_surface(*, event_id, member_id, role):
    from apps.makerspaces.platform import feature_enabled
    event = Event.objects.select_related("makerspace").filter(pk=event_id).first()
    if not event:
        return False
    if not feature_enabled(event.makerspace, "events.mentoring" if role == "mentor" else "events.hackathons"):
        return False
    try:
        page = visible_page(event)
    except Http404:
        return False
    from apps.events.website_content import group_enabled
    if (not page or not group_enabled(page, "SPEAKERS") or not page.sections.filter(
            kind="mentors" if role == "mentor" else "judges", visibility="published").exists()):
        return False
    return EventRoleAssignment.objects.filter(event_id=event_id, member_id=member_id, role=role,
        state="approved", imported_inert=False, display_on_page=True).exists()


def mentor_surface(**kwargs):
    return role_surface(**kwargs, role="mentor")


def judge_surface(**kwargs):
    return role_surface(**kwargs, role="judge")


def team_surface(*, event_id, member_id):
    from apps.events.submissions.gallery_models import GalleryEntry
    from apps.events.submissions.gallery_projection import live_entry
    from apps.events.judging.ports import runtime
    from apps.makerspaces.editions import public_surface_available
    from apps.makerspaces.platform import module_enabled
    from apps.makerspaces.servability import is_servable
    from rest_framework.exceptions import APIException
    event = Event.objects.select_related("makerspace").filter(pk=event_id, is_public=True,
        status__in=("published", "completed")).first()
    if not event or not (event.makerspace.public_site_enabled and is_servable(event.makerspace)
            and module_enabled(event.makerspace, "events") and public_surface_available("events")):
        return False
    try:
        runtime().require_programme(event, gallery=True)
        for entry in GalleryEntry.objects.filter(event_id=event_id, hidden_at=None, publication__active=True):
            snapshot, _ = live_entry(entry)
            if member_id in snapshot.member_ids and HackathonTeamMember.objects.filter(event_id=event_id,
                    team_id=snapshot.team_id, member_id=member_id, state="active").exists():
                return True
    except (Http404, APIException):
        return False
    return False


def public_member_card(*, event_id, member_id, scope):
    value = project_public(event_id=event_id, member_id=member_id, scope=scope)
    if value is None:
        return None
    # E uses `name`; D's closed projection requires a handle and display_name.
    handle = urlsplit(value["profile_url"]).path.strip("/")
    return {"handle": handle, "display_name": value["name"],
            "profile_url": f"/{handle}", "photo_url": value.get("photo_url")}


def install():
    from apps.events.profile_photos.policy import register_subject, register_public_surface
    register_subject("application", application_subject)
    register_subject("contributor", role_subject)
    for scope, predicate in (("team", team_surface), ("mentor", mentor_surface), ("judge", judge_surface)):
        register_public_surface(scope, predicate)
