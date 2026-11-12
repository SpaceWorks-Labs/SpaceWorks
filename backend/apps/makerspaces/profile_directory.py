"""The per-space member directory, driven by the global account profile (decision 304e).

A space still lists ONLY its own active members, and only display name, headline and avatar --
never anything else from the profile. A member with no profile row yet gets the open defaults
(visible, empty headline); one who hid their profile (`is_visible` false) or whose account is
restricted/suspended becomes part of `hidden_count` and nothing else.

The detail read (SECURITY-REVIEW H1) is built from the MEMBER-audience payload of the global profile
(`account_profile_read.build_payload`), so every section switch, the per-project "shown" flag and
the https-only link filter apply exactly as on the profile page; it is then only re-shaped into the
legacy per-space response. Owner state (visibility, open-web consent, the raw switches) is never
part of it.
"""

from django.db.models import Q

from apps.inventory import public_image_storage
from apps.makerspaces.account_profile_read import account_is_listable, build_payload
from apps.makerspaces.models import AccountProfile, MakerspaceMembership
from apps.makerspaces.profile_services import display_name_for, profile_activity


def _listable(user, profile):
    # The one listability rule of the global profile (L-P5): person, active, not restricted, not a stub.
    return account_is_listable(user) and (profile is None or profile.is_visible)


def directory(makerspace, query=""):
    """Visible members, plus a count of everyone who is not shown."""
    memberships = MakerspaceMembership.objects.filter(
        makerspace=makerspace, status="active", user__is_active=True
    ).select_related("user", "user__account_profile")
    query = (query or "").strip()[:200]
    if query:
        memberships = memberships.filter(
            Q(user__username__icontains=query) | Q(user__display_name__icontains=query)
            | Q(user__first_name__icontains=query) | Q(user__last_name__icontains=query)
            | Q(user__account_profile__headline__icontains=query)
            | Q(user__account_profile__institution__icontains=query)
        )
    members, hidden = [], 0
    for membership in memberships:
        profile = getattr(membership.user, "account_profile", None)
        if not _listable(membership.user, profile):
            hidden += 1
            continue
        members.append({
            "membership_id": membership.pk,
            "display_name": display_name_for(membership),
            "headline": profile.headline if profile else "",
            "avatar_url": (public_image_storage.public_url(profile.avatar_key) or None) if profile else None,
        })
    members.sort(key=lambda row: row["display_name"].lower())
    return {"members": members, "hidden_count": hidden}


def _legacy_shape(membership, payload, activity):
    shown = payload["shown"]
    space_name = membership.makerspace.name
    return {
        "verified": membership.verified_at is not None, "membership_id": membership.pk,
        "display_name": payload["display_name"], "handle": payload["handle"], "is_visible": True,
        "public_consented_at": None,
        "show_attended_events": shown["events"], "show_certifications": shown["certifications"],
        "certifications": [row["name"] for row in payload["certifications"] if row["space_name"] == space_name],
        "headline": payload["headline"], "institution": payload["institution"], "bio": payload["bio"],
        "avatar_url": payload["avatar_url"], "interests": payload["interests"],
        "languages": payload["languages"], "education": payload["education"],
        "domains": payload["domains"], "skills": payload["skills"], "links": payload["links"],
        "github_username": payload["github_username"], "github_contributions": payload["github_contributions"],
        "github_verified": payload["github_verified"], "projects": payload["projects"], "activity": activity,
    }


def _empty(user):
    from apps.makerspaces.account_profile import display_name_for_user
    from apps.makerspaces.account_profile_read import handle_for
    from apps.makerspaces.models_account_profile import SECTION_TOGGLES

    return {"shown": {name.removeprefix("show_"): False for name in SECTION_TOGGLES},
            "display_name": display_name_for_user(user), "handle": handle_for(user), "certifications": [],
            "headline": "", "institution": "", "bio": "", "avatar_url": None, "interests": [], "languages": [],
            "education": [], "domains": [], "skills": [], "links": [], "github_username": "",
            "github_contributions": None, "github_verified": False, "projects": []}


def visible_profile(makerspace, membership_id, *, viewer=None, local_activity_only=False):
    """One other member's profile (legacy shape), or None when it is not theirs to show."""
    membership = MakerspaceMembership.objects.select_related("user", "makerspace").filter(
        pk=membership_id, makerspace=makerspace, status="active", user__is_active=True
    ).first()
    if membership is None:
        return None
    profile = AccountProfile.objects.filter(user=membership.user).select_related("user").first()
    if not _listable(membership.user, profile):
        return None
    # Reads never create a row: a member with no profile yet has only the open, empty defaults.
    payload = build_payload(profile, "member", viewer) if profile is not None else _empty(membership.user)
    activity = profile_activity(membership, local_only=local_activity_only) if payload["shown"]["events"] else {}
    return _legacy_shape(membership, payload, activity)
