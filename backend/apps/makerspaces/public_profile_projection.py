"""Build public payloads without ever reading the private profile serializer."""

from urllib.parse import urlsplit
from apps.inventory.public_image_storage import public_url
from .models import MembershipVouch
from .models_profiles import PublicHandle
from .profile_services import display_name_for
from .public_profile_access import profile_is_public
from .platform import module_enabled


def https_links(rows):
    result = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        try:
            url = urlsplit(row.get("url", ""))
            if url.scheme == "https" and url.hostname and not url.username and not url.password:
                result.append({"kind": row.get("kind", row.get("label", "")), "url": row["url"]})
        except (TypeError, ValueError):
            continue
    return result[:10]


def public_project(row):
    return {"title": row.title, "subtitle": row.subtitle, "description": row.description,
            "tags": row.tags, "links": https_links(row.links),
            "image_url": public_url(row.image_key) or None}


def public_projects(profile):
    return profile.projects.filter(public_visible=True) if profile.show_projects else profile.projects.none()


def _vouches(profile):
    membership = profile.membership
    vouchers = MembershipVouch.objects.filter(makerspace=membership.makerspace,
                                             request__user=membership.user).values_list("voucher_id", flat=True)
    vouchees = MembershipVouch.objects.filter(makerspace=membership.makerspace,
                                             voucher=membership.user).values_list("request__user_id", flat=True)
    # Only chosen, live public profiles in THIS space can contribute either names
    # or counts; an anonymous count must not reveal privately vouched members.
    claims = PublicHandle.objects.filter(profile__membership__makerspace=membership.makerspace).select_related(
        "profile__membership__user", "profile__membership__makerspace")
    named = []
    for claim in claims.filter(user_id__in=vouchers):
        if profile_is_public(claim.profile):
            named.append({"handle": claim.handle, "display_name": display_name_for(claim.profile.membership)})
    count = sum(profile_is_public(claim.profile) for claim in claims.filter(user_id__in=vouchees))
    return named, count


def public_profile_payload(claim):
    profile = claim.profile
    named, count = _vouches(profile)
    payload = {
        "handle": claim.handle, "display_name": display_name_for(profile.membership),
        "avatar_url": public_url(profile.avatar_key) or None,
        "verified": profile.membership.verified_at is not None,
        "headline": profile.headline, "institution": profile.institution, "bio": profile.bio,
        "domains": profile.domains, "skills": profile.skills, "links": https_links(profile.links),
        "timeline": profile.timeline.all(),
        "projects": [public_project(row) for row in public_projects(profile)],
        "vouched_by": named, "vouched_count": count,
    }
    for field in ("show_activity_graph", "show_events", "show_speaking", "show_projects",
                  "show_machine_activity", "show_bookings", "show_loans"):
        payload[field] = getattr(profile, field)
    return payload


def public_events(profile):
    if not profile.show_events or not module_enabled(profile.membership.makerspace, "events"):
        return []
    from .profile_activity_sources import attended_registrations
    from apps.events.models import Event
    return Event.objects.filter(pk__in=attended_registrations(profile).order_by().values_list(
        "event_id", flat=True)).select_related("makerspace").order_by("-starts_at", "-pk")


def public_event(event):
    return {"title": event.title, "starts_at": event.starts_at, "ends_at": event.ends_at,
            "badge": "ATTENDED", "host": event.makerspace.name}
