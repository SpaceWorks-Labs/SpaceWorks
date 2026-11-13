"""Legacy-shaped profile reads/writes for the deprecated per-space routes, backed by the account profile.

The real implementation is `account_profile` (writes) and `account_profile_read` (reads). This
module only translates the OLD request/response shape (one profile "in" a membership) to and from
the account profile, so shipped clients keep working. The activity-graph family switches and the GitHub
username are account-level too (decision 304c) and read/write the account profile.
"""

from django.db import transaction

from apps.accounts.account_kind_guards import require_member_account
from apps.inventory import public_image_storage

from . import account_profile
from .account_profile import display_name_for_user
from .public_profile_handles import PublicHandle

RECENT_ATTENDED_EVENTS_LIMIT = 20
LEGACY_PUBLICATION_FLAGS = ("show_activity_graph", "show_speaking", "show_machine_activity",
                            "show_bookings", "show_loans")


def display_name_for(membership):
    return display_name_for_user(membership.user)


def profile_for(membership):
    """The account profile of the membership's user (legacy name kept for callers)."""
    require_member_account(membership.user)
    return account_profile.account_profile_for(membership.user)


def profile_activity(membership, *, local_only=False):
    """Counts of what this member has done; module-disabled sections stay absent, not zero."""
    from apps.makerspaces.platform import module_enabled

    from .account_profile_activity import attended_events

    activity = {}
    if module_enabled(membership.makerspace, "events"):
        from apps.events.member_history import registrations_for_space
        from apps.events.models import EventRegistration

        registrations = registrations_for_space(membership.makerspace, membership.user)
        activity["events_attended"] = registrations.filter(status=EventRegistration.Status.ATTENDED).count()
        activity["events_registered"] = registrations.exclude(status=EventRegistration.Status.CANCELLED).count()
        if account_profile.AccountProfile.objects.filter(user=membership.user, show_events=True).exists():
            only = membership.makerspace_id if (
                local_only or getattr(membership.user, "_claim_audit_context", None) is not None) else None
            activity["recent_attended_events"] = [
                {"id": row["id"], "title": row["title"], "starts_at": row["starts_at"]}
                for row in attended_events(membership.user, only)["recent"]]
    return activity


def read_profile(membership, *, include_activity=True, local_activity_only=False):
    """The account profile in the legacy per-membership shape. Reads never create a row."""
    from .models_account_profile import AccountProfile

    user = membership.user
    profile = AccountProfile.objects.filter(user=user).first() or AccountProfile(user=user)
    projects = profile.projects.all() if profile.pk else ()
    handle = PublicHandle.objects.filter(user_id=user.pk).values_list("handle", flat=True).first()
    certifications = []
    if profile.show_certifications:
        from apps.machines.certifications import live_certification_names
        certifications = list(live_certification_names(membership))
    from .profile_github import github_verified as _verified

    github_verified = bool(profile.pk and _verified(profile))
    payload = {
        "verified": membership.verified_at is not None, "membership_id": membership.pk,
        "display_name": display_name_for(membership), "is_visible": profile.is_visible,
        "show_attended_events": profile.show_events, "show_certifications": profile.show_certifications,
        "certifications": certifications, "headline": profile.headline, "institution": profile.institution,
        "bio": profile.bio, "avatar_url": public_image_storage.public_url(profile.avatar_key) or None,
        "interests": profile.interests or [], "languages": profile.languages or [],
        "education": profile.education or [],
        "github_username": profile.github_username,
        "github_contributions": profile.github_contributions if github_verified else None,
        "github_verified": github_verified,
        "projects": [{"id": p.pk, "title": p.title, "subtitle": p.subtitle, "tags": p.tags,
                      "public_visible": p.public_visible, "description": p.description,
                      "links": p.links or [], "image_url": public_image_storage.public_url(p.image_key) or None,
                      "imported": p.source_submission_id is not None} for p in projects],
        "activity": profile_activity(membership, local_only=local_activity_only) if include_activity else {},
        "public_visible": profile.public_visible, "public_consented_at": profile.public_consented_at,
        "show_events": profile.show_events, "show_projects": profile.show_projects,
        "domains": profile.domains or [], "skills": profile.skills or [], "links": profile.links or [],
        "handle": handle,
    }
    payload.update({flag: getattr(profile, flag) for flag in LEGACY_PUBLICATION_FLAGS})
    return payload


@transaction.atomic
def save_profile(membership, data):
    """Translate the old write shape onto the account profile and save it there."""
    require_member_account(membership.user)
    mapped = {key: value for key, value in data.items() if key != "show_attended_events"}
    if "show_attended_events" in data:
        mapped["show_events"] = data["show_attended_events"]
    return account_profile.save_profile(membership.user, mapped, makerspace=membership.makerspace)


from .profile_directory import directory, visible_profile  # noqa: E402,F401

__all__ = ["directory", "display_name_for", "profile_activity", "profile_for", "read_profile",
           "save_profile", "visible_profile"]
