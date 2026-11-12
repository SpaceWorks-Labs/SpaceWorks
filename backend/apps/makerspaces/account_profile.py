"""The account-level profile: creation, the owner's writes and the audit trail (decisions 302-305).

Creation is lazy (`account_profile_for`) and also happens on account creation (signal in
`account_profile_signals`). Creating a row publishes nothing beyond the open default of decision
303a -- name, headline and avatar of an empty profile -- and auto-claims the username as handle
when it is available (305c addendum).
"""

from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext
from rest_framework.exceptions import ValidationError

from apps.accounts.account_kind_guards import require_member_account
from apps.audit import services as audit

from .models_account_profile import ACTIVITY_TOGGLES, SECTION_TOGGLES, AccountProfile

CONTENT_FIELDS = (
    "headline", "status", "status_note", "institution", "bio", "domains", "skills", "links",
    "interests", "languages", "education",
)
SWITCH_FIELDS = ("is_visible", *SECTION_TOGGLES, *ACTIVITY_TOGGLES)


def display_name_for_user(user):
    return user.display_name or user.get_full_name().strip() or user.username


def ensure_legacy_pointers(user):
    """One empty legacy `MemberProfile` per ACTIVE membership, as an identity token (decision 305).

    Stored references (page team members, event website revisions, event photo selections, certificate
    print sources) name a `MemberProfile` row, and published revisions are immutable, so they cannot be
    re-pointed. The row carries no content of its own: visibility comes from the account profile
    (`public_profile_access.profile_is_public`) and the photo from the avatar mirrored by `mirror_avatar`.
    """
    from .models import MakerspaceMembership

    for membership in MakerspaceMembership.all_tracks.filter(user=user, status="active", track="community"):
        ensure_legacy_pointer(membership)


def ensure_legacy_pointer(membership):
    """The one token for ONE membership. Idempotent; called by membership activation and lazily."""
    from .models_profiles import MemberProfile

    avatar = getattr(AccountProfile.objects.filter(user_id=membership.user_id).first(), "avatar_key", "")
    return MemberProfile.objects.get_or_create(membership=membership, defaults={"avatar_key": avatar})[0]


def mirror_avatar(user, object_key):
    """Keep the pointer rows' `avatar_key` equal to the account avatar for photo-source consumers."""
    from .models_profiles import MemberProfile

    from django.utils import timezone

    # `updated_at` doubles as the photo-source revision of event photo selections, so it moves too.
    MemberProfile.objects.filter(membership__user=user).update(avatar_key=object_key, updated_at=timezone.now())


def account_profile_for(user):
    """The account's profile row, created on demand; a new row claims the default handle."""
    require_member_account(user)
    profile = AccountProfile.objects.filter(user=user).first()
    if profile is not None:
        return profile
    with transaction.atomic():
        # H5 / decision 336b: a profile is open by default, so its owner is told once (the hourly
        # notice sweep), however the row came to exist -- sign-up, backfill or a lazy read.
        profile, created = AccountProfile.objects.get_or_create(user=user, defaults={"open_notice_pending": True})
    if created:
        ensure_legacy_pointers(user)
        from .public_profile_handles import claim_default_handle

        claim_default_handle(user)
        audit.record(user, "member.profile_opened", target=user, meta={})
    return profile


def _apply_open_web(profile, data, fields):
    """`public_visible` is the open-web consent (303b): turning it on needs fresh consent."""
    if "public_visible" not in data:
        return
    if data["public_visible"] and not profile.public_visible:
        if data.get("publication_consent") is not True:
            raise ValidationError({"publication_consent": gettext("Fresh consent is required to publish.")})
        from .account_profile_minors import guardian_consented

        # H4 / decision 336a: a minor cannot open their profile to the web alone; the guardian
        # consent recorded through the space's guardian flow must be current.
        if not guardian_consented(profile.user):
            raise ValidationError({"public_visible": gettext(
                "A guardian's consent is needed before this profile can be shown on the open web.")})
        profile.public_consented_at = timezone.now()
    if data["public_visible"] is False:
        profile.public_consented_at = None
    profile.public_visible = data["public_visible"]
    # Any explicit open-web choice answers the merge's re-confirmation request (decision 335c).
    profile.public_reconfirm_pending = False
    fields += ["public_visible", "public_consented_at", "public_reconfirm_pending"]


@transaction.atomic
def save_profile(user, data, *, makerspace=None):
    """Apply a partial update; a `projects` list replaces the project list."""
    require_member_account(user)
    account_profile_for(user)
    profile = AccountProfile.objects.select_for_update().get(user=user)
    before = {name: getattr(profile, name) for name in SWITCH_FIELDS}
    public_before = profile.public_visible
    project_count_before = profile.projects.count()
    fields = []
    for field in (*CONTENT_FIELDS, *SWITCH_FIELDS):
        if field in data:
            setattr(profile, field, data[field])
            fields.append(field)
    _apply_open_web(profile, data, fields)
    if "github_username" in data and data["github_username"].strip() != profile.github_username:
        # A new username invalidates the cached count outright: leaving the previous account's total
        # under someone else's name would be a false claim, not stale data.
        profile.github_username = data["github_username"].strip()
        profile.github_contributions = None
        profile.github_synced_at = None
        fields += ["github_username", "github_contributions", "github_synced_at"]
        if profile.github_username:
            from .profile_github_queue import queue_verification

            queue_verification(user.pk)  # decision 338: verify now, not at tomorrow's sweep
    if fields:
        profile.save(update_fields=[*dict.fromkeys(fields), "updated_at"])
    if "projects" in data:
        from .profile_projects import save_projects

        save_projects(profile, data["projects"])
    sections = sorted(name for name in (*SECTION_TOGGLES, *ACTIVITY_TOGGLES) if getattr(profile, name) != before[name])
    audit.record(
        user, "member.profile_updated", makerspace=makerspace, target=user,
        meta={
            "fields": sorted(set(fields)),
            "visibility_changed": before["is_visible"] != profile.is_visible,
            "is_visible": profile.is_visible,
            "sections_changed": sections,
            "attended_events_shown": profile.show_events,
            "attended_events_changed": "show_events" in sections,
            "certifications_shown": profile.show_certifications,
            "open_web_changed": public_before != profile.public_visible,
            "projects_before": project_count_before,
            "projects_after": profile.projects.count(),
        },
    )
    return profile
