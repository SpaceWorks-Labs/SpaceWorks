"""Reading and writing a member's own profile, and the member-visible directory."""

from django.db import transaction

from apps.audit import services as audit
from apps.inventory import public_image_storage
from apps.makerspaces.models import MakerspaceMembership, MemberProfile, MemberProject

RECENT_ATTENDED_EVENTS_LIMIT = 20


def profile_for(membership):
    """The membership's profile row, created on demand.

    Created rather than returned as defaults so every later write has a row to lock and
    a stable id to hang project rows and image keys off. It is empty and invisible, so
    creating one publishes nothing.
    """
    profile, _ = MemberProfile.objects.get_or_create(membership=membership)
    return profile


def display_name_for(membership):
    user = membership.user
    return user.display_name or user.get_full_name().strip() or user.username


def _published_certifications(membership, profile):
    """Live certification names, only once the member has opted in (consent, not config)."""
    if not profile.show_certifications:
        return []
    from apps.machines.certifications import live_certification_names

    return list(live_certification_names(membership))


def read_profile(membership, *, include_activity=True, local_activity_only=False):
    # Reads must not call the write-side ``profile_for`` helper. An unsaved model
    # instance gives serializers the model defaults without publishing a row merely
    # because somebody opened the page.
    profile = MemberProfile.objects.filter(membership=membership).first()
    projects = profile.projects.all() if profile is not None else ()
    profile = profile or MemberProfile(membership=membership)
    payload = {
        "verified": membership.verified_at is not None,
        "membership_id": membership.pk,
        "display_name": display_name_for(membership),
        "is_visible": profile.is_visible,
        "show_attended_events": profile.show_attended_events,
        "show_certifications": profile.show_certifications,
        "certifications": _published_certifications(membership, profile),
        "headline": profile.headline,
        "institution": profile.institution,
        "bio": profile.bio,
        "avatar_url": public_image_storage.public_url(profile.avatar_key) or None,
        "interests": profile.interests or [],
        "languages": profile.languages or [],
        "education": profile.education or [],
        "github_username": profile.github_username,
        "github_contributions": profile.github_contributions,
        "projects": [
            {
                "id": project.pk,
                "title": project.title,
                "subtitle": project.subtitle,
                "tags": project.tags,
                "public_visible": project.public_visible,
                "description": project.description,
                "links": project.links or [],
                "image_url": public_image_storage.public_url(project.image_key) or None,
            }
            for project in projects
        ],
        "activity": profile_activity(
            membership, local_only=local_activity_only
        ) if include_activity else {},
    }
    from .public_profile_validation import PUBLICATION_FIELDS
    payload.update({field: getattr(profile, field) for field in PUBLICATION_FIELDS})
    payload["public_consented_at"] = profile.public_consented_at
    from .models_profiles import PublicHandle
    payload["handle"] = PublicHandle.objects.filter(profile=profile).values_list("handle", flat=True).first() if profile.pk else None
    return payload


def profile_activity(membership, *, local_only=False):
    """Counts of what this member has done in THIS space.

    Derived, never stored: a stored counter drifts the moment a registration is
    cancelled. Each section is omitted when its module is off rather than reported as
    zero -- a zero says "attended nothing", an absent key says "this space does not run
    events", and they are not the same statement.
    """
    from apps.makerspaces.platform import module_enabled

    activity = {}
    makerspace = membership.makerspace
    if module_enabled(makerspace, "events"):
        from apps.events.member_history import registrations_for_space
        from apps.events.models import EventRegistration

        registrations = registrations_for_space(makerspace, membership.user)
        if local_only or getattr(membership.user, "_claim_audit_context", None) is not None:
            registrations = registrations.filter(event__makerspace=makerspace)
        activity["events_attended"] = registrations.filter(
            status=EventRegistration.Status.ATTENDED
        ).count()
        # Cancellations are excluded: "registered for 40 events" is not a truthful
        # summary of someone who cancelled thirty of them.
        activity["events_registered"] = registrations.exclude(
            status=EventRegistration.Status.CANCELLED
        ).count()
        # Read the consent flag straight from the row, deliberately NOT through
        # `membership.profile` or `profile_for`. `get_or_create(membership=...)` populates
        # the reverse one-to-one cache on the membership instance, and `save_profile`
        # re-reads the row through a *separate* instance -- so anything saving twice on one
        # membership object would then gate publication on a stale copy of the flag. A
        # privacy gate must not depend on which instance happened to warm a cache. This
        # also stops a read path from creating a row, which `profile_for` would.
        show_attended_events = MemberProfile.objects.filter(
            membership=membership
        ).values_list("show_attended_events", flat=True).first()
        if show_attended_events:
            recent = (
                registrations.filter(status=EventRegistration.Status.ATTENDED)
                .select_related("event")
                .only("event__id", "event__title", "event__starts_at")
                # `-id` is a tiebreaker, not decoration: two events can share a
                # `starts_at`, and without it the cap could include a different subset
                # on each request. `member_activity_service` orders the same way.
                .order_by("-event__starts_at", "-id")[:RECENT_ATTENDED_EVENTS_LIMIT]
            )
            activity["recent_attended_events"] = [
                {
                    "id": registration.event.id,
                    "title": registration.event.title,
                    "starts_at": registration.event.starts_at,
                }
                for registration in recent
            ]
    return activity


@transaction.atomic
def save_profile(membership, data):
    """Apply a partial profile update, replacing the project list when one is sent."""
    MakerspaceMembership.objects.select_for_update().get(pk=membership.pk)
    profile = MemberProfile.objects.select_for_update().filter(
        membership=membership
    ).first() or profile_for(membership)
    was_visible = profile.is_visible
    attended_events_were_shown = profile.show_attended_events
    project_count_before = profile.projects.count()
    fields = []
    for field in (
        "is_visible", "show_attended_events", "show_certifications", "headline",
        "institution", "bio", "interests", "languages", "education",
    ):
        if field in data:
            setattr(profile, field, data[field])
            fields.append(field)
    from .public_profile_validation import apply_publication, PUBLICATION_FIELDS
    if any(field in data for field in PUBLICATION_FIELDS):
        apply_publication(profile, data)
        fields.extend(field for field in PUBLICATION_FIELDS if field in data)
    if "github_username" in data:
        username = (data["github_username"] or "").strip()
        if username != profile.github_username:
            # A new handle invalidates the cached count outright rather than leaving the
            # previous account's total showing under someone else's name until the next
            # sync — which would be a false claim, not merely stale data.
            profile.github_username = username
            profile.github_contributions = None
            profile.github_synced_at = None
            fields += ["github_username", "github_contributions", "github_synced_at"]
    if fields:
        profile.save(update_fields=[*fields, "updated_at"])
    if "projects" in data:
        save_projects(profile, data["projects"])
    _audit_profile_saved(
        membership,
        profile,
        was_visible,
        attended_events_were_shown,
        project_count_before,
        fields,
    )
    return profile


def _audit_profile_saved(
    membership,
    profile,
    was_visible,
    attended_events_were_shown,
    project_count_before,
    fields,
):
    """Record that the profile changed, without copying its contents into the log.

    The audit log is append-only and makerspace-scoped, so it must say *what changed*
    and by whom — but writing profile contents or derived event details into it would
    copy member PII into a store that is deliberately impossible to edit or delete. The
    meta therefore names the fields touched and the boolean publication transitions.
    """
    profile.refresh_from_db(fields=["is_visible", "show_attended_events", "show_certifications"])
    audit.record(
        membership.user,
        "member.profile_updated",
        makerspace=membership.makerspace,
        target=membership,
        meta={
            "fields": sorted(fields),
            "visibility_changed": was_visible != profile.is_visible,
            "is_visible": profile.is_visible,
            "attended_events_shown": profile.show_attended_events,
            "certifications_shown": profile.show_certifications,
            "attended_events_changed": (
                attended_events_were_shown != profile.show_attended_events
            ),
            "projects_before": project_count_before,
            "projects_after": profile.projects.count(),
        },
    )


from .profile_projects import save_projects  # noqa: E402


# The member-visible directory lives in its own module (file-size ceiling); re-exported so
# `profile_services.directory` / `.visible_profile` keep resolving for views and tests.
from apps.makerspaces.profile_directory import directory, visible_profile  # noqa: E402

__all__ = [
    "directory", "display_name_for", "profile_activity", "profile_for", "read_profile",
    "save_profile", "save_projects", "visible_profile",
]
