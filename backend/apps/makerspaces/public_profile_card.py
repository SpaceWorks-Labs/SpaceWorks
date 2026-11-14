"""Decision 549: the always-on, allow-listed public account card.

This projection never calls the rich owner/member reader. In particular, being
signed in cannot reveal additional fields through a public handle read.
"""

from django.utils import timezone
from rest_framework.exceptions import NotFound

from apps.accounts.staff_identity import is_person
from apps.inventory.public_image_storage import public_url
from .account_profile_minors import is_minor_account
from .account_profile_spaces import listed_memberships, listed_space_ids, _public_space, _public_role_title
from .models_account_profile import AccountProfile
from .local_time import to_local
from .models_profiles import PublicHandle, PublicHandleRedirect
from .public_profile_access import _request_tenant_ids
from .public_profile_projection import public_project


def resolve_card_handle(handle, request=None):
    """Resolve a live personal handle without creating a profile or changing data."""
    claim = PublicHandle.objects.filter(handle__iexact=handle, user__isnull=False).select_related("user").first()
    redirected = False
    if claim is None:
        retired = PublicHandleRedirect.objects.filter(
            handle__iexact=handle, expires_at__gt=timezone.now(), user__isnull=False).first()
        if retired:
            claim = PublicHandle.objects.filter(user_id=retired.user_id).select_related("user").first()
            redirected = claim is not None
    if claim is None or not is_person(claim.user) or not claim.user.is_active or claim.user.is_tenant_dump_stub:
        raise NotFound()
    # Keep Host AND browser-origin tenant fences, even though the card is public.
    if request is not None:
        scopes = _request_tenant_ids(request)
        if scopes and not set(scopes) <= listed_space_ids(claim.user):
            raise NotFound()
    return claim, redirected


def public_memberships(user):
    """One public row per space; staff title wins, earliest membership date wins."""
    rows = {}
    for membership in listed_memberships(user):
        space = membership.makerspace
        if not _public_space(space):
            continue
        # A malformed cross-tenant role must never disclose another tenant's title.
        if membership.assigned_role_id and membership.assigned_role.makerspace_id != space.pk:
            continue
        start = to_local(space, membership.activated_at or membership.created_at).date()
        row = rows.setdefault(space.pk, {
            "slug": space.slug, "name": space.name, "role_title": None, "started_on": start,
        })
        row["started_on"] = min(row["started_on"], start)
        if membership.track == "staff" or row["role_title"] is None:
            row["role_title"] = _public_role_title(membership) or row["role_title"]
    return sorted(rows.values(), key=lambda row: (row["name"].casefold(), row["slug"]))


def public_card(claim):
    user = claim.user
    profile = AccountProfile.objects.filter(user_id=user.pk).first()
    # Login usernames may contain a private email; the chosen public handle is the safe fallback.
    card = {"display_name": user.display_name or user.get_full_name().strip() or claim.handle,
            "avatar_url": (public_url(profile.avatar_key) or None) if profile else None}
    if user.access_status != "active" or is_minor_account(user):
        return card
    card.update({
        "handle": claim.handle,
        "bio": profile.bio if profile and profile.show_about else "",
        "projects": [public_project(row) for row in profile.projects.filter(public_visible=True)]
        if profile and profile.show_projects else [],
        "memberships": public_memberships(user),
    })
    return card
