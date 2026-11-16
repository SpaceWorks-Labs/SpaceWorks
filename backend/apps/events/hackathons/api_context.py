"""Token-only account bootstrap; reads never create application/vault/membership."""
from django.utils.translation import gettext
from copy import deepcopy
from zoneinfo import ZoneInfo
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import APIException
from apps.events.models import Event
from apps.events.registration_access import require_registration_access
from apps.events.website_visibility import resolve
from apps.makerspaces.platform import feature_enabled
from .admission_errors import fail
from .admission_models import HackathonApplication, HackathonConfig, HackathonCocRevision
from .admission_ports import ports
from .admission_projection import admission_requirements, project_owner
from .admission_transactions import require_member

CAPABILITIES = ("events.hackathons", "events.mentoring", "events.mentor_rounds",
                "events.volunteering", "events.project_gallery")


def event_context(event):
    return {"event_id": event.pk, "event_date_revision": event.event_date_revision,
            "timezone_name": event.timezone_name,
            "as_of_date": event.starts_at.astimezone(ZoneInfo(event.timezone_name)).date().isoformat()}


def form_descriptor(event, schema):
    result = deepcopy(schema)
    if isinstance(result, dict):
        result["event_context"] = event_context(event)
    return result


def routes_for(event, *, hackathon, eligible):
    member = f"/api/v1/member/makerspaces/{event.makerspace_id}/events/{event.pk}"
    def named(name, url):
        return {"name": name, "url": url}
    routes = {"member_base": member,
        "context": named("events-programme-public-context", f"/api/v1/public/event-programmes/{event.public_token}/context/")}
    for key, suffix in (("application", ""), ("application_submit", "submit/"),
                        ("application_withdraw", "withdraw/"), ("application_rsvp", "rsvp/"),
                        ("application_date_review", "date-review/")):
        name = "events-programme-member-application-" + (suffix.strip("/") or "detail")
        routes[key] = named(name, member + "/application/" + suffix) if hackathon and eligible else None
    routes["role_postings"] = named("events-programme-member-role-posting-list", member + "/role-postings/") if eligible and feature_enabled(event.makerspace, "events.volunteering") else None
    routes["prefill"] = named("member-saved-details-prefill", "/api/v1/member/saved-details/prefill/") if eligible else None
    routes["ordinary_register"] = named("public-event-register", f"/api/v1/public/{event.makerspace.slug}/events/{event.public_token}/register/") if eligible and not hackathon else None
    return routes


def context_for_token(*, public_token, actor, request=None):
    require_member(actor)
    event = resolve(None, public_token)
    # G's token origin resolver must run before selected-context assumptions.
    ports().context_gate(event=event, actor=actor, request=request)
    config = HackathonConfig.objects.filter(event=event, enabled=True).first()
    capabilities = {key: feature_enabled(event.makerspace, key) for key in CAPABILITIES}
    # Applications for any one-off event (#128 C-32) share the engine; `kind` tells the two apart.
    hackathon = capabilities["events.hackathons"]
    if config and not (hackathon or feature_enabled(event.makerspace, "events.applications")):
        fail("not_found", gettext("Not found."), status=404)
    eligible, reason = True, None
    try:
        require_registration_access(event, actor)
    except APIException as exc:
        if exc.status_code != 403:
            raise
        eligible, reason = False, str(exc.detail.get("code", "audience_required")) if isinstance(exc.detail, dict) else "audience_required"
    details = event_context(event)
    coc = get_object_or_404(HackathonCocRevision, event=event, revision=config.coc_revision) if config else None
    own_registration = None
    if eligible:
        own_registration = event.registrations.filter(member=actor).first()
    return {"context_version": 1,
        "event": {"id": event.pk, "public_token": str(event.public_token),
                  "starts_at": event.starts_at, "ends_at": event.ends_at,
                  **{key: value for key, value in details.items() if key != "event_id"}},
        "makerspace": {"id": event.makerspace_id, "slug": event.makerspace.slug},
        "programme": {"kind": ("hackathon" if hackathon else "applications") if config else "ordinary", "capabilities": capabilities,
                      "team_mode": config.team_mode if config else None, "finder_enabled": bool(config and config.finder_enabled)},
        "application_form": form_descriptor(event, config.application_form) if config else None,
        "registration_form": None if config else form_descriptor(event, event.custom_form),
        "coc": {"revision": coc.revision, "body": coc.body} if coc else None,
        "admission_requirements": admission_requirements(event, actor, request=request, registration=own_registration),
        "eligibility": {"eligible": eligible, "reason": reason},
        "saved_details": {"readiness": ports().readiness(actor_id=actor.pk) if eligible else "unavailable"},
        "routes": routes_for(event, hackathon=bool(config), eligible=eligible)}


def owner_application(*, event, config, actor, request=None):
    application = HackathonApplication.objects.filter(event=event, member=actor).first()
    return project_owner(application, event=event, actor=actor,
                         form=form_descriptor(event, config.application_form),
                         coc={"revision": config.coc_revision, "body": get_object_or_404(HackathonCocRevision, event=event, revision=config.coc_revision).body}, request=request)
