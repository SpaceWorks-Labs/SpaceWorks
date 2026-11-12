import hashlib

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.accounts.models_social import SocialIdentity, SocialSurface
from apps.accounts.principal_guards import is_anonymous_requester
from apps.accounts.staff_identity import PERSON_KIND, is_person, person_q


class SocialResolutionError(Exception):
    def __init__(self, code, status_code):
        super().__init__(code)
        self.code = code
        self.status_code = status_code


def resolve_social_identity(
    *, provider, claims, surface, apple_name="", explicit_user=None,
    staff_validator=None, allow_auto_link=True, allow_user_creation=True
):
    """Resolve a provider subject to a local user.

    `allow_auto_link` is what a generic OIDC provider can turn off. Matching an existing
    account by email is only safe when the provider genuinely verifies email ownership;
    an operator running an IdP that does not should set it false, and an email match then
    demands an explicit link instead of silently handing over the account.
    """
    if surface != SocialSurface.MEMBER:
        raise SocialResolutionError("social_invalid", 403)
    subject = claims["sub"]
    with transaction.atomic():
        identity = (
            SocialIdentity.objects.select_for_update()
            .select_related("user")
            .filter(provider=provider, provider_sub=subject)
            .first()
        )
        if explicit_user is not None:
            return _explicit_link(identity, explicit_user, provider, subject)
        if identity is not None:
            if not is_person(identity.user):
                raise SocialResolutionError("social_invalid", 403)
            if staff_validator is not None:
                staff_validator(identity.user)
            return identity.user, "existing"

        email = claims.get("email") or ""
        verified = bool(email and claims.get("email_verified"))
        matched = None
        if email:
            matched = (
                User.objects.select_for_update()
                .filter(person_q(), email__iexact=email)
                .exclude(email="")
                .first()
            )
        if matched is not None:
            # A walk-in is a person record staff typed at the counter, not an account, so
            # an external credential must never come to own it -- the same rule the two
            # password-reset paths enforce. Today `email_verified_at is None` already
            # refuses it, but that is an accident of walk-ins having no way to verify an
            # address rather than a statement about walk-ins; saying it directly means the
            # rule holds even if that ever changes.
            if (
                not allow_auto_link
                or not verified
                or matched.email_verified_at is None
                or matched.is_walk_in
                or is_anonymous_requester(matched)
            ):
                raise SocialResolutionError("account_link_required", 409)
            user = matched
            outcome = "auto_linked"
        else:
            # A deployment with registration disabled may still link existing members.
            if not allow_user_creation:
                raise SocialResolutionError("registration_disabled", 403)
            user = User(
                username=_available_username(provider, subject),
                account_kind=PERSON_KIND,
                email=email if verified else "",
                display_name=(apple_name or claims.get("name") or "")[:200],
                role=User.Role.REQUESTER,
                access_status=User.AccessStatus.ACTIVE,
                email_verified_at=timezone.now() if verified else None,
            )
            user.set_unusable_password()
            try:
                user.save()
                # Decision 308: a handle is claimed atomically with the account. The provider flow
                # is a redirect with no form, so the best suggestion is taken here and the person
                # may change it once without the 30-day wait (the blocking step is for accounts
                # that end up with none).
                from apps.makerspaces.public_profile_handles import claim_for_signup
                claim_for_signup(user)
            except IntegrityError as exc:
                # A concurrent member signup/provider login may claim the email or
                # username after our lookup. Roll back; a fresh login resolves it.
                raise SocialResolutionError("identity_conflict", 409) from exc
            outcome = "created"
        if staff_validator is not None:
            staff_validator(user)
        try:
            # The savepoint must roll back before the winner lookup below. A caught
            # uniqueness error otherwise leaves the outer transaction unusable.
            with transaction.atomic():
                SocialIdentity.objects.create(
                    user=user, provider=provider, provider_sub=subject
                )
        except IntegrityError:
            winner = SocialIdentity.objects.select_related("user").filter(
                provider=provider, provider_sub=subject
            ).first()
            if winner is None or winner.user_id != user.pk:
                raise SocialResolutionError("identity_conflict", 409) from None
        return user, outcome


def _explicit_link(identity, user, provider, subject):
    user = User.objects.select_for_update().get(pk=user.pk)
    # Migration 0015 cannot revoke an access token during its 15-minute lifetime.
    # Keep this guard here, rather than at the caller branch, because every explicit
    # social-identity link is created through this function.
    if not is_person(user):
        raise SocialResolutionError("social_invalid", 403)
    if user.is_walk_in:
        raise SocialResolutionError("walk_in_record", 403)
    if is_anonymous_requester(user):
        raise SocialResolutionError("anonymous_requester_record", 403)
    if identity is not None:
        if identity.user_id != user.pk:
            raise SocialResolutionError("identity_conflict", 409)
        return user, "existing"
    current = SocialIdentity.objects.select_for_update().filter(
        user=user, provider=provider
    ).first()
    if current is not None:
        raise SocialResolutionError("provider_already_linked", 409)
    try:
        SocialIdentity.objects.create(user=user, provider=provider, provider_sub=subject)
    except IntegrityError as exc:
        raise SocialResolutionError("identity_conflict", 409) from exc
    return user, "linked"


def unlink_social_identity(user, provider):
    # One "would this strand them?" answer for every guard: a verified phone or a passkey is
    # a way in too, so a member who has one may drop their last provider (credential_inventory).
    from apps.accounts.credential_inventory import would_strand

    with transaction.atomic():
        locked = User.objects.select_for_update().get(pk=user.pk)
        identity = SocialIdentity.objects.select_for_update().filter(
            user=locked, provider=provider
        ).first()
        if identity is None:
            raise SocialResolutionError("identity_not_found", 404)
        if would_strand(locked, drop_identity_pk=identity.pk):
            raise SocialResolutionError("last_credential", 409)
        identity.delete()


def _available_username(provider, subject):
    digest = hashlib.sha256(f"{provider}:{subject}".encode()).hexdigest()[:24]
    # An OIDC provider key is `oidc:<slug>`, and Django's username validator rejects a
    # colon. The digest still keys on the unsanitized provider, so two providers whose
    # slugs differ only by a colon cannot collide.
    base = f"{provider.replace(':', '_')}_{digest}"
    candidate = base
    suffix = 1
    while User.objects.filter(username=candidate).exists():
        suffix += 1
        candidate = f"{base}_{suffix}"
    return candidate
