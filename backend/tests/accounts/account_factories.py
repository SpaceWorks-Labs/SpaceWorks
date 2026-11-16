"""Explicit valid account contexts for tests of unrelated account workflows."""

from django.db import transaction

from apps.accounts.models import User
from apps.makerspaces.models import MakerspaceMembership, MakerspaceRole


@transaction.atomic
def make_staff(makerspace, *, username, role_slug="space_manager", password=None, **fields):
    """One account per person: a person holding a staff-TRACK row with the given role."""
    role = MakerspaceRole.objects.get(makerspace=makerspace, slug=role_slug)
    fields.setdefault("role", "space_manager" if role_slug == "space_manager" else "requester")
    user = User.objects.create_user(username=username, password=password, **fields)
    grant_staff_role(user, makerspace, role_slug=role_slug)
    return user


def grant_staff_role(user, makerspace, *, role_slug="space_manager", status="active"):
    """Give an existing person a staff-track row (fixture shortcut, no authority checks)."""
    role = MakerspaceRole.objects.get(makerspace=makerspace, slug=role_slug)
    return MakerspaceMembership.staff_tracks.create(
        user=user, makerspace=makerspace, track=MakerspaceMembership.Track.STAFF,
        assigned_role=role, role=role.legacy_role or "custom", status=status)


def make_membership(user, makerspace, *, status="active", **fields):
    """Member fixtures always use the tenant's seeded Member role."""
    role = MakerspaceRole.objects.get(makerspace=makerspace, slug="member")
    return MakerspaceMembership.objects.create(user=user, makerspace=makerspace,
        assigned_role=role, role=role.legacy_role or "custom", status=status, **fields)


def device_grant(user, registration=None, *, platform="android", app_id="test.app",
                 environment="development", **fields):
    """A grant satisfying the native-account context for a person.

    Member grants carry no staff tenant. Pass ``staff_makerspace_id`` for a staff grant:
    password-issued, MFA-gated, attested and fixed to a space where the person holds an
    active staff-track row (DB-enforced).
    """
    from django.utils import timezone

    from apps.accounts.models import DeviceGrant, NativeAppRegistration
    from apps.accounts.models_mfa import UserMFA

    if registration is None:
        # One approved deployment registration per platform/environment (DB-enforced):
        # reuse it whatever its app id rather than creating a second one.
        registration = NativeAppRegistration.objects.filter(
            makerspace=None, platform=platform, environment=environment,
            status=NativeAppRegistration.Status.APPROVED,
        ).first()
    if registration is None:
        registration, _ = NativeAppRegistration.objects.get_or_create(
            makerspace=None, app_id=app_id, platform=platform, environment=environment,
            defaults={"verifier_config_key": app_id, "status": NativeAppRegistration.Status.APPROVED},
        )
    now = timezone.now()
    fields.setdefault("signing_identity", f"TEAM.{registration.app_id}")
    fields.setdefault("attestation_subject_fingerprint", "f" * 64)
    fields.setdefault("attested_at", now)
    fields.setdefault("last_used_at", now)
    staff_space = fields.pop("staff_makerspace_id", None)
    if staff_space is not None:
        UserMFA.objects.get_or_create(user=user, defaults={"enabled_at": now})
        fields.update(authority="staff", staff_makerspace_id=staff_space, login_method="password")
    return DeviceGrant.objects.create(
        registration=registration, user=user, platform=registration.platform,
        app_id=registration.app_id, environment=registration.environment,
        credential_generation=user.credential_generation, **fields,
    )
