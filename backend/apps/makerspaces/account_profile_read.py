"""Build profile payloads per audience (decisions 303, 304). One builder, three audiences.

Audiences: ``owner`` (everything, including switches and consent state), ``member`` (any signed-in
user, anywhere on the platform) and ``public`` (logged out). `member` and `public` see the SAME
content -- the open-web consent only decides whether `public` may see the profile at all -- and a
section whose switch is off is returned empty with its `shown` flag false, so a hidden section and
an empty one are indistinguishable only by the flag, never by content.

The spaces section narrows further by WHO reads it (decision 336b, SECURITY-REVIEW M13): a
``viewer`` who shares an active space with the person also sees role titles and vouches; everyone
else sees only public spaces and public organisations, with no role titles and no vouches.
"""

from urllib.parse import urlsplit

from apps.accounts.staff_identity import is_person
from apps.inventory.public_image_storage import public_url

from . import account_profile_activity as activity
from .account_profile import SWITCH_FIELDS, display_name_for_user
from .models_account_profile import ACTIVITY_TOGGLES, SECTION_TOGGLES
from .models_profiles import PublicHandle
from .profile_achievements import achievements


def https_links(rows):
    result = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        try:
            url = urlsplit(row.get("url", ""))
        except ValueError:
            continue
        if url.scheme == "https" and url.hostname and not url.username and not url.password:
            result.append({"kind": row.get("kind", row.get("label", "")), "url": row["url"]})
    return result[:10]


def account_is_listable(user):
    """A restricted, suspended, inactive, retired or stub account has no readable profile."""
    return bool(is_person(user) and user.is_active and user.access_status == "active"
                and not user.is_tenant_dump_stub)


def handle_for(user):
    return PublicHandle.objects.filter(user_id=user.pk).values_list("handle", flat=True).first()


def _timeline(profile):
    return [{"id": e.pk, "kind": e.kind, "title": e.title, "organization": e.organization,
             "location": e.location, "start": e.start, "end": e.end, "description": e.description,
             "order": e.order} for e in profile.timeline.all()]


def _projects(profile, *, owner):
    rows = profile.projects.all() if owner else profile.projects.filter(public_visible=True)
    return [{"id": p.pk, "title": p.title, "subtitle": p.subtitle, "tags": p.tags,
             "public_visible": p.public_visible, "description": p.description,
             "links": p.links if owner else https_links(p.links),
             "image_url": public_url(p.image_key) or None,
             "imported": p.source_submission_id is not None} for p in rows]


def _spaces_section(profile, audience, viewer):
    from .account_profile_minors import shared_space_ids
    from .account_profile_spaces import spaces_and_organizations
    from .account_profile_vouches import vouches_for

    user = profile.user
    if audience == "owner":
        return {**spaces_and_organizations(user, full=True), **vouches_for(user, audience)}
    shared = shared_space_ids(user, viewer) if audience == "member" else set()
    section = spaces_and_organizations(user, shared_ids=shared)
    vouches = vouches_for(user, audience) if shared else {"vouched_by": [], "vouched_count": 0}
    return {**section, **vouches}


def _certifications(user, audience, viewer):
    """Other readers only see certifications from spaces they may see (M13)."""
    from .account_profile_minors import shared_space_ids
    from .account_profile_spaces import visible_memberships

    if audience == "owner":
        return activity.certifications(user)
    shared = shared_space_ids(user, viewer) if audience == "member" else set()
    return activity.certifications(user, visible_memberships(user, shared_ids=shared))


def _github_verified(profile, owner):
    from .profile_github import github_verified

    return bool(profile.github_username and (owner or profile.show_activity_graph)
                and github_verified(profile))


def build_payload(profile, audience, viewer=None):
    owner = audience == "owner"
    user = profile.user
    shown = {name.removeprefix("show_"): getattr(profile, name) for name in SECTION_TOGGLES}

    def gate(section, value, empty):
        return value if owner or shown[section] else empty

    spaces = {"spaces": [], "organizations": [], "vouched_by": [], "vouched_count": 0}
    if owner or profile.show_spaces:
        spaces = _spaces_section(profile, audience, viewer)
    payload = {
        "audience": audience,
        "handle": handle_for(user),
        "account_id": user.pk,
        "display_name": display_name_for_user(user),
        "avatar_url": public_url(profile.avatar_key) or None,
        "headline": profile.headline,
        "institution": profile.institution,
        "shown": shown,
        "status": gate("status", {"preset": profile.status, "note": profile.status_note}, None),
        "bio": gate("about", profile.bio, ""),
        "timeline": [e for e in _timeline(profile) if owner or shown[
            "education" if e["kind"] == "education" else "experience"]],
        "education": gate("education", profile.education or [], []),
        "skills": gate("skills", profile.skills if owner else profile.skills, []),
        "domains": gate("skills", profile.domains or [], []),
        "links": gate("links", profile.links if owner else https_links(profile.links), []),
        "interests": gate("interests", profile.interests or [], []),
        "languages": gate("interests", profile.languages or [], []),
        "projects": _projects(profile, owner=owner) if owner or shown["projects"] else [],
        "achievements": achievements(profile) if owner or shown["achievements"]
        else {"verified": [], "self_reported": []},
        "events_attended": activity.attended_events(user) if owner or shown["events"]
        else {"count": 0, "recent": []},
        "certifications": _certifications(user, audience, viewer) if owner or shown["certifications"] else [],
        **spaces,
        "activity_shown": {name.removeprefix("show_"): getattr(profile, name) for name in ACTIVITY_TOGGLES},
        # The GitHub identity is only shown when the person switched the activity graph on.
        "github_username": profile.github_username if owner or profile.show_activity_graph else "",
        "github_contributions": profile.github_contributions if _github_verified(profile, owner) else None,
        # Decision 338 (L-P4): the badge and calendar are for a username proven to be the owner's
        # linked GitHub sign-in; anything else is a plain, unverified link.
        "github_verified": _github_verified(profile, owner),
    }
    if not owner:
        # Row ids are the owner's edit handles; nobody else needs them (and a logged-out reader must
        # not learn an account id at all).
        for key in ("timeline", "projects"):
            payload[key] = [{k: v for k, v in row.items() if k != "id"} for row in payload[key]]
        payload["achievements"]["self_reported"] = [
            {k: v for k, v in row.items() if k != "id"} for row in payload["achievements"]["self_reported"]]
        if audience == "public":
            payload["account_id"] = None
    if owner:
        payload.update({
            "is_visible": profile.is_visible, "public_visible": profile.public_visible,
            "public_consented_at": profile.public_consented_at,
            "public_reconfirm_pending": profile.public_reconfirm_pending,
            "toggles": {name: getattr(profile, name) for name in SWITCH_FIELDS},
        })
    return payload
