"""Live checks shared by printing, C/D cards and the public photo gateway."""

from rest_framework.exceptions import NotFound

from apps.events.models_registration import EventRegistration
from apps.makerspaces.platform import module_enabled
from apps.makerspaces.public_profile_access import profile_is_public
from apps.makerspaces.servability import is_servable

_subjects = {}
_public_surfaces = {}


def source_open(makerspace_id):
    from apps.backup.not_restored import TenantNotRestored
    from apps.tenant_migration.gate_errors import SourceMigrationGateClosed
    from apps.tenant_migration.gate_runtime import assert_write_allowed
    try:
        assert_write_allowed(makerspace_id)
        return True
    except (TenantNotRestored, SourceMigrationGateClosed):
        return False


def register_subject(name, predicate):
    """G installs A/C owner eligibility providers at startup, without ORM at import."""
    if name in _subjects and _subjects[name] is not predicate:
        raise ValueError("Subject provider already installed.")
    _subjects[name] = predicate


def register_public_surface(scope, predicate):
    """C/D/pages supply live display_on_page + release/gallery checks. Default deny."""
    if scope not in ("team", "mentor", "judge") or (scope in _public_surfaces and _public_surfaces[scope] is not predicate):
        raise ValueError("Unknown or duplicate public card surface.")
    _public_surfaces[scope] = predicate


def active_member(actor):
    return bool(actor and actor.is_authenticated and actor.account_kind == "member"
                and actor.is_active and actor.access_status == "active" and not actor.is_tenant_dump_stub)


def require_owner_event(event, actor):
    if (not active_member(actor) or not is_servable(event.makerspace)
            or not module_enabled(event.makerspace, "events")):
        raise NotFound()
    registered = EventRegistration.objects.filter(event=event, member=actor).exclude(
        status__in=("cancelled", "rejected"),
    ).exists()
    if not registered and not any(check(event_id=event.pk, member_id=actor.pk) for check in _subjects.values()):
        raise NotFound()


def source_live(profile, member_id):
    membership = profile.membership
    return bool(membership.user_id == member_id and active_member(membership.user)
                and membership.status == "active" and is_servable(membership.makerspace)
                and module_enabled(membership.makerspace, "membership")
                and source_open(membership.makerspace_id))


def print_profile(presentation):
    if not presentation or not presentation.print_photo_consent or not presentation.selected_profile_id:
        return None
    profile = presentation.selected_profile
    if (profile.membership_id != presentation.selected_membership_id
            or not source_live(profile, presentation.member_id) or not profile.avatar_key):
        return None
    return profile


def public_profile(presentation, scope):
    if (scope not in presentation.public_card_scopes or not presentation.public_card_consent
            or not presentation.selected_profile_id or scope not in _public_surfaces):
        return None
    event = presentation.event
    profile = presentation.selected_profile
    if (profile.membership_id != presentation.selected_membership_id
            or not source_live(profile, presentation.member_id) or not profile_is_public(profile)
            or not is_servable(event.makerspace) or not module_enabled(event.makerspace, "events")
            or not source_open(event.makerspace_id)
            or not _public_surfaces[scope](event_id=event.pk, member_id=presentation.member_id)):
        return None
    from apps.makerspaces.models_profiles import PublicHandle
    claim = PublicHandle.objects.filter(profile=profile, user_id=presentation.member_id).first()
    return (profile, claim) if claim else None
