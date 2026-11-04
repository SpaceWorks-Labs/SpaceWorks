"""Derived readiness; inaccessible actions and their counts are never queried."""

from django.utils import timezone

from apps.events import event_authority
from apps.events.event_permissions import EDIT_DETAILS, MANAGE_REGISTRATIONS, VIEW
from apps.makerspaces.platform import feature_enabled

from .providers import readiness_providers
from .aggregate import aggregate


EXPECTED_SUMMARIES = (
    ("coc", "Review code of conduct", "applications", "events.hackathons", "manage_hackathon"),
    ("team_limits", "Review team limits", "teams", "events.hackathons", "manage_hackathon"),
    ("storage", "Review upload storage", "submissions", "events.hackathons", "manage_hackathon"),
    ("rubric", "Configure judging rubric", "judging", "events.hackathons", None),
    ("judge_coverage", "Check judge coverage", "judging", "events.hackathons", None),
    ("mentors", "Check mentor coverage", "mentoring", "events.mentoring", "mentor_queue"),
    ("door_shifts", "Check door shift coverage", "volunteers", "events.volunteering", "manage_volunteers"),
    ("certificates", "Configure certificates", "certificates", "events.certificate_designer", None),
    ("reviews", "Applications waiting for review", "applications", "events.hackathons", "review_applications"),
    ("help", "Teams waiting for help", "mentoring", "events.mentoring", "mentor_queue"),
    ("approvals", "Contributors waiting for approval", "roles", "events.volunteering", "manage_volunteers"),
)


def event_href(event, tab):
    return f"/admin/events?event={event.pk}&tab={tab}"


def item(event, code, label, ready, tab, *, count=None, action=False):
    return {"code": code, "label": label, "status": "ready" if ready else (
        "action" if action else "missing"), "href": event_href(event, tab), "count": count}


def project_readiness(event, *, actor, now=None):
    event_authority.require(actor, event, VIEW)
    envelope = aggregate(event, actor)
    now = now or timezone.now()
    items = []
    if event_authority.can(actor, event, EDIT_DETAILS):
        for code, label, ready, tab in (
            ("dates", "Set event dates", bool(event.starts_at and event.ends_at
                                               and event.ends_at >= event.starts_at), "overview"),
            ("visibility", "Choose event visibility", event.status != "draft", "publishing"),
            ("cover", "Add a cover photo", bool(event.image_key), "cover"),
            ("form", "Review registration questions", event.custom_form is not None, "forms"),
        ):
            items.append(item(event, code, label, ready, tab))
    if event_authority.can(actor, event, MANAGE_REGISTRATIONS):
        count = event.registrations.filter(status="pending_approval").count()
        items.append(item(event, "registration_approvals", "Registrations waiting for you", count == 0,
                          "registrations", count=count, action=True))
    providers = readiness_providers()
    installed = {provider.key for provider in providers}
    for code, label, tab, feature, permission in EXPECTED_SUMMARIES:
        if (code not in installed and event_authority.can(actor, event, permission)
                and feature_enabled(event.makerspace, feature)):
            items.append({"code": code, "label": label, "status": "unavailable",
                          "href": event_href(event, tab), "count": None})
    for provider in providers:
        if (not event_authority.can(actor, event, provider.permission)
                or not feature_enabled(event.makerspace, provider.feature)):
            continue
        # Providers return only derived status/count; callers never pass raw private rows.
        summary = provider.summarize(event=event, actor=actor)
        if summary is None:
            continue
        status, count = summary["status"], summary.get("count")
        if status not in {"ready", "missing", "action", "unavailable"}:
            raise ValueError("Invalid readiness status from provider.")
        if count is not None and (type(count) is not int or count < 0):
            raise ValueError("Invalid readiness count from provider.")
        items.append({"code": provider.key, "label": provider.label, "status": status,
                      "href": event_href(event, provider.tab), "count": count})
    return {**envelope, "generated_at": now, "items": items}
