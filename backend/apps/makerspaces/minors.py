"""Decision 223 (k), lane L3b: marking a minor, publishing guardian terms, and the e-signed consent.

Minimum stored: a birth date OR an "under age" declaration (never both required), plus how to reach the
guardian (an account, or a name and contact). Birth date, guardian contact and the typed signature are
scoped PII. The audit log carries ids, versions and field names only, never a date of birth, a contact
detail, a signature or the consent text.

Consent is versioned like `MakerspaceWaiver`: one active text per space; signing records which version
was signed. A consent counts only for the CURRENT terms version, so publishing new terms asks guardians
again, exactly as a new waiver asks members again.
"""
from datetime import date, timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import APIException, ValidationError

from apps.audit import services as audit
from apps.makerspaces.community_policy import CommunityError, policy_for
from apps.makerspaces.models import GuardianConsent, GuardianConsentTerms, MinorProfile
from django.utils.translation import gettext


class GuardianTermsConflict(APIException):
    status_code = 409
    default_code = "guardian_terms_conflict"
    default_detail = "Another publish of the guardian terms just completed. Reload and try again."


def _write_gate(makerspace):
    from apps.encryption.write_fence import assert_mapped_write_allowed
    from apps.tenant_migration.gate_runtime import assert_write_allowed
    assert_write_allowed(makerspace.pk)
    assert_mapped_write_allowed(makerspace.pk)


def _local_today(makerspace):
    """m13: "today" on the space's own clock, not the server's."""
    from apps.makerspaces.local_time import to_local
    return to_local(makerspace, timezone.now()).date() if makerspace is not None else timezone.localdate()


def parse_birth_date(value, today=None, makerspace=None):
    today = today or _local_today(makerspace)
    try:
        born = date.fromisoformat(value)
    except (TypeError, ValueError):
        raise ValidationError({"date_of_birth": gettext("Use a date as YYYY-MM-DD.")})
    if born > today or born.year < today.year - 120:
        raise ValidationError({"date_of_birth": gettext("Enter a real birth date.")})
    return born


def years_since(born_iso, today=None, makerspace=None):
    today = today or _local_today(makerspace)
    born = date.fromisoformat(born_iso)
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))


def age_of(profile, today=None):
    """Whole years, or None when only an "under age" declaration was recorded."""
    return years_since(profile.date_of_birth, today, profile.makerspace) if profile.date_of_birth else None


def is_minor(profile, policy, today=None):
    if profile is None or profile.cleared_at is not None:
        return False
    age = age_of(profile, today)
    return profile.declared_under_age if age is None else age < policy.adult_age


def profile_for(makerspace, user):
    return MinorProfile.objects.filter(makerspace=makerspace, user=user).first() if user is not None else None


def active_terms(makerspace):
    return GuardianConsentTerms.objects.filter(makerspace=makerspace, is_active=True).first()


def current_consent(profile, now=None):
    """The newest unrevoked, unexpired consent for the CURRENT terms version, or None."""
    now = now or timezone.now()
    terms = active_terms(profile.makerspace)
    if terms is None:
        return None
    return GuardianConsent.objects.filter(
        profile=profile, terms=terms, revoked_at__isnull=True, valid_until__gt=now).order_by("-signed_at").first()


def record_minor(actor, makerspace, user, *, date_of_birth="", declared_under_age=False, guardian_user=None,
                 guardian_name="", guardian_email="", guardian_phone=""):
    """Staff (`manage_members`, checked by the view) mark an account as a minor, or update the record."""
    policy = policy_for(makerspace)
    if date_of_birth:
        born = parse_birth_date(date_of_birth, makerspace=makerspace)
        if years_since(born.isoformat(), makerspace=makerspace) >= policy.adult_age:
            raise ValidationError({"date_of_birth": gettext("This person is not under the age of majority here.")})
    elif not declared_under_age:
        raise ValidationError({"date_of_birth": gettext("Give a birth date, or declare the person under age.")})
    if guardian_user is not None and guardian_user.pk == user.pk:
        raise ValidationError({"guardian_user": gettext("A person cannot be their own guardian.")})
    _write_gate(makerspace)
    with transaction.atomic():
        profile = MinorProfile.objects.select_for_update().filter(makerspace=makerspace, user=user).first()
        created = profile is None
        profile = profile or MinorProfile(makerspace=makerspace, user=user)
        profile.date_of_birth = date_of_birth or ""
        profile.declared_under_age = bool(declared_under_age) and not date_of_birth
        profile.guardian_user = guardian_user
        profile.guardian_name = (guardian_name or "").strip()
        profile.guardian_email = (guardian_email or "").strip().lower()
        profile.guardian_phone = (guardian_phone or "").strip()
        profile.recorded_by, profile.cleared_at = actor, None
        profile.save()
        audit.record(actor, "membership.minor_recorded", makerspace=makerspace, target=profile,
                     meta={"created": created, "has_guardian_account": guardian_user is not None})
        from .notifications_guardian import notify_requested
        notify_requested(profile)
    return profile


def clear_minor(actor, profile):
    """The person is no longer treated as a minor (came of age, or recorded by mistake). Consents stay as history."""
    _write_gate(profile.makerspace)
    with transaction.atomic():
        row = MinorProfile.objects.select_for_update().select_related("makerspace").get(pk=profile.pk)
        if row.cleared_at is None:
            row.cleared_at = timezone.now()
            row.save(update_fields=["cleared_at", "updated_at"])
            audit.record(actor, "membership.minor_cleared", makerspace=row.makerspace, target=row)
    return row


def publish_terms(actor, makerspace, body, version):
    """Publish new guardian-consent text. The previous active version is kept, superseded."""
    body, version = (body or "").strip(), (version or "").strip()
    if not body or not version:
        raise ValidationError({"body": gettext("Give the consent text and a version.")})
    try:
        with transaction.atomic():
            # Lock the space row so concurrent publishes run one after the other; the unique
            # version / single-active constraints stay as the backstop, mapped to a typed 409.
            type(makerspace).objects.select_for_update().filter(pk=makerspace.pk).first()
            if GuardianConsentTerms.objects.filter(makerspace=makerspace, version=version).exists():
                raise ValidationError({"version": gettext("This version already exists.")})
            now = timezone.now()
            GuardianConsentTerms.objects.filter(makerspace=makerspace, is_active=True).update(
                is_active=False, superseded_at=now)
            terms = GuardianConsentTerms.objects.create(
                makerspace=makerspace, body=body, version=version, created_by=actor)
            audit.record(actor, "membership.guardian_terms_published", makerspace=makerspace, target=terms,
                         meta={"version": version})
    except IntegrityError as exc:
        raise GuardianTermsConflict() from exc
    from .notifications_guardian import notify_terms_changed
    notify_terms_changed(makerspace)  # existing guardians are asked again for the new version
    return terms


def sign_consent(actor, profile, signed_name, *, accepted, method, operation_id=None, now=None):
    """Record a guardian's e-signature on the current terms.

    `method="guardian_account"`: the actor IS the profile's guardian account. `method="staff_recorded"`: staff
    (the view checks `manage_members`) record a signature taken on paper or at the desk.
    """
    now = now or timezone.now()
    if accepted is not True or not (signed_name or "").strip():
        raise CommunityError("consent_not_accepted", gettext("Accept the terms and type your full name to sign."), 400)
    makerspace = profile.makerspace
    terms = active_terms(makerspace)
    if terms is None:
        raise CommunityError("guardian_terms_missing", gettext("This space has not published guardian consent terms yet."), 409)
    if method == GuardianConsent.Method.GUARDIAN_ACCOUNT and profile.guardian_user_id != actor.pk:
        raise CommunityError("not_the_guardian", gettext("Only the named guardian can sign in their own account."))
    _write_gate(makerspace)
    with transaction.atomic():
        row = MinorProfile.objects.select_for_update().get(pk=profile.pk)
        if operation_id:
            replay = GuardianConsent.objects.filter(makerspace=makerspace, operation_id=operation_id).first()
            if replay is not None:
                if replay.profile_id != row.pk:  # m16: another person's id is a client bug, never a replay
                    raise CommunityError("operation_id_reused", gettext("That operation id belongs to a different record."), 409)
                return replay
        valid_days = policy_for(makerspace).consent_valid_days
        consent = GuardianConsent.objects.create(
            profile=row, makerspace=makerspace, terms=terms, terms_version=terms.version, method=method,
            signed_name=signed_name.strip()[:200], recorded_by=actor,
            guardian_user=actor if method == GuardianConsent.Method.GUARDIAN_ACCOUNT else row.guardian_user,
            signed_at=now, valid_until=now + timedelta(days=valid_days), operation_id=operation_id or None)
        audit.record(actor, "membership.guardian_consent_signed", makerspace=makerspace, target=consent,
                     meta={"terms_version": terms.version, "method": method})
    return consent


def revoke_consent(actor, consent):
    _write_gate(consent.makerspace)
    with transaction.atomic():
        row = GuardianConsent.objects.select_for_update().select_related("makerspace").get(pk=consent.pk)
        if row.revoked_at is None:
            row.revoked_at, row.revoked_by = timezone.now(), actor
            row.save(update_fields=["revoked_at", "revoked_by"])
            audit.record(actor, "membership.guardian_consent_revoked", makerspace=row.makerspace, target=row)
    return row
