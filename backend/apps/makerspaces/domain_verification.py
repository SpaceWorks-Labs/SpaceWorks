import dns.resolver
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.makerspaces.hosting import canonical_host
from apps.makerspaces.models import Makerspace

EXPECTED_HOST_PREFIX = "_spaceworks-verify"
LEGACY_EXPECTED_HOST_PREFIX = "_osmm-verify"
EXPECTED_HOST_PREFIXES = (EXPECTED_HOST_PREFIX, LEGACY_EXPECTED_HOST_PREFIX)
DOMAIN_CHANGE_COOLDOWN_MESSAGE = (
    "You changed your domain recently; please wait before changing it again."
)


def is_self_host() -> bool:
    """Self-host mode = no platform suffix configured. In that mode the operator
    controls both DNS and the server, so a SUPERADMIN-set custom domain is trusted
    without the TXT challenge that defends the shared managed box. A Space-Manager-set
    domain is not the operator's word, so it passes the same TXT challenge (#192)."""
    return not str(settings.PLATFORM_DOMAIN_SUFFIX or "").strip()


def is_operator(actor) -> bool:
    """The platform superadmin: on self-host, their word is the operator's."""
    from apps.accounts.models import User
    return bool(actor is not None and (actor.is_superuser or actor.role == User.Role.SUPERADMIN))


def expected_record(makerspace):
    """The TXT record that proves control of the domain, or None when none is needed:
    no domain, or a self-host domain already trusted (the operator's, or one that passed)."""
    if not makerspace.frontend_domain:
        return None
    if is_self_host() and makerspace.frontend_domain_status == Makerspace.DomainStatus.VERIFIED:
        return None
    return {
        "host": f"{EXPECTED_HOST_PREFIX}.{makerspace.frontend_domain}",
        "type": "TXT",
        "value": makerspace.domain_verification_token,
    }


def _resolve_txt(name):
    resolver = dns.resolver.Resolver()
    resolver.timeout = 5
    resolver.lifetime = 5
    answers = resolver.resolve(name, "TXT")
    return [
        b"".join(part for part in answer.strings).decode("utf-8")
        for answer in answers
    ]


def resolves_to_origin(makerspace) -> bool:
    configured_origin = str(settings.PLATFORM_ORIGIN_HOST or "").strip()
    if not configured_origin:
        return True

    domain = canonical_host(makerspace.frontend_domain or "")
    origin = canonical_host(configured_origin)
    if domain is None or origin is None:
        return False

    try:
        resolver = dns.resolver.Resolver()
        resolver.timeout = 5
        resolver.lifetime = 5
        try:
            cname_answers = resolver.resolve(domain, "CNAME")
        except dns.resolver.NoAnswer:
            cname_answers = ()
        if any(
            canonical_host(str(answer.target)) == origin
            for answer in cname_answers
        ):
            return True

        domain_addresses = {str(answer) for answer in resolver.resolve(domain, "A")}
        origin_addresses = {str(answer) for answer in resolver.resolve(origin, "A")}
        return bool(domain_addresses & origin_addresses)
    except Exception:
        return False


def passkey_only_accounts(makerspace) -> int:
    """People whose only second factor is a passkey on this space's custom-domain RP ID.

    A domain change strands their passkey sign-in on the old address (passkeys are bound
    to it); the passkey still counts as their factor, so nobody is downgraded to "no
    factor", but they need their password and recovery codes, or another factor, on the
    new address. Shown before a change so the operator can warn them first.
    """
    if not makerspace.frontend_domain:
        return 0
    from apps.accounts.models import User
    from apps.accounts.models_mfa import UserMFA
    from apps.accounts.models_webauthn import WebAuthnCredential
    from apps.accounts.passkeys.rp_id import rp_id_for_host
    rp_id = rp_id_for_host(canonical_host(makerspace.frontend_domain))
    on_domain = WebAuthnCredential.objects.filter(rp_id=rp_id).values("user_id")
    elsewhere = WebAuthnCredential.objects.exclude(rp_id=rp_id).values("user_id")
    totp = UserMFA.objects.filter(enabled_at__isnull=False).values("user_id")
    return User.objects.filter(pk__in=on_domain).exclude(pk__in=elsewhere).exclude(pk__in=totp).count()


def domain_change_cooldown_active(makerspace, normalized_domain) -> bool:
    cooldown_seconds = settings.DOMAIN_CHANGE_COOLDOWN_SECONDS
    return bool(
        cooldown_seconds > 0
        and makerspace is not None
        and normalized_domain != makerspace.frontend_domain
        and makerspace.frontend_domain_changed_at is not None
        and (timezone.now() - makerspace.frontend_domain_changed_at).total_seconds()
        < cooldown_seconds
    )


def apply_domain_change(makerspace, frontend_domain, *, operator_trusted) -> None:
    """The one status transition for a changed ``frontend_domain`` (unsaved).

    VERIFIED is the trust gate for CORS, staff origins, Host validation and on-demand
    TLS, so a new host must never inherit the old host's VERIFIED. Self-host trusts a
    superadmin-set domain (``operator_trusted``) at once; a Space-Manager-set one on
    self-host, and every one on managed hosting, goes to PENDING until the TXT challenge
    passes (#192). Every writer -- the staff serializer and the /control/ form -- calls
    this rather than restating it; the caller owns the authority check.
    """
    now = timezone.now()
    makerspace.frontend_domain_changed_at = now
    if is_self_host() and frontend_domain and operator_trusted:
        makerspace.frontend_domain_status = Makerspace.DomainStatus.VERIFIED
        makerspace.domain_verified_at = now
    else:
        makerspace.frontend_domain_status = Makerspace.DomainStatus.PENDING
        makerspace.domain_verified_at = None


def _is_platform_managed(domain) -> bool:
    suffix = str(settings.PLATFORM_DOMAIN_SUFFIX or "").strip().lower()
    canonical = canonical_host(domain or "")
    if not suffix or not canonical:
        return False
    return canonical == suffix.lstrip(".") or canonical.endswith(suffix)


def _require_manage_under_lock(actor, makerspace):
    """The view authorized before a DNS lookup that can take seconds; re-check under the
    row lock so a grant revoked meanwhile cannot still write the trust-gating status."""
    from apps.accounts import rbac
    from apps.makerspaces.authority_lock import require_under_lock

    require_under_lock(
        actor, makerspace.pk,
        lambda: rbac.can(actor, rbac.Action.MANAGE_MAKERSPACE, makerspace.pk),
    )


def _commit_status(makerspace, target, status, *, set_verified_at, detail, actor):
    """Persist a verification outcome, but re-read the row under a lock first so a
    concurrent domain change can never have this (slow, DNS-based) result written
    onto a different — and unverified — hostname. The status gates host admission
    and on-demand TLS, so a stale write would trust an unchecked domain."""
    with transaction.atomic():
        locked = Makerspace.objects.select_for_update().get(pk=makerspace.pk)
        _require_manage_under_lock(actor, locked)
        if locked.frontend_domain != target:
            makerspace.frontend_domain_status = locked.frontend_domain_status
            makerspace.domain_verified_at = locked.domain_verified_at
            return (
                locked.frontend_domain_status,
                locked.domain_verified_at,
                "Domain changed during verification; please re-run.",
            )
        locked.frontend_domain_status = status
        fields = ["frontend_domain_status", "updated_at"]
        if set_verified_at:
            locked.domain_verified_at = timezone.now()
            fields.insert(1, "domain_verified_at")
        locked.save(update_fields=fields)
        makerspace.frontend_domain_status = locked.frontend_domain_status
        makerspace.domain_verified_at = locked.domain_verified_at
        return (locked.frontend_domain_status, locked.domain_verified_at, detail)


def verify_domain(makerspace, *, actor):
    """Run one verification attempt for ``actor``, who must hold MANAGE_MAKERSPACE.

    The caller authorizes first; every write below re-checks that authority under the
    makerspace row lock (`authority_lock`), so the check and the write cannot race apart.
    """
    if not makerspace.frontend_domain:
        with transaction.atomic():
            locked = Makerspace.objects.select_for_update().get(pk=makerspace.pk)
            _require_manage_under_lock(actor, locked)
            if locked.frontend_domain:
                return (
                    locked.frontend_domain_status,
                    locked.domain_verified_at,
                    "Domain changed during verification; please re-run.",
                )
            locked.frontend_domain_status = Makerspace.DomainStatus.PENDING
            locked.domain_verified_at = None
            locked.save(
                update_fields=[
                    "frontend_domain_status",
                    "domain_verified_at",
                    "updated_at",
                ]
            )
        makerspace.frontend_domain_status = Makerspace.DomainStatus.PENDING
        makerspace.domain_verified_at = None
        return (Makerspace.DomainStatus.PENDING, None, "No custom domain set.")

    target = makerspace.frontend_domain
    # Self-host: the operator owns DNS and the server, so the superadmin's word trusts a
    # domain immediately. A Space Manager proves control with the TXT record below
    # (#192); a domain already trusted stays trusted, so their re-check never drops the
    # operator's decision.
    if is_self_host() and is_operator(actor):
        return _commit_status(
            makerspace,
            target,
            Makerspace.DomainStatus.VERIFIED,
            set_verified_at=True,
            actor=actor,
            detail="Self-hosted custom domain set by the platform operator — trusted automatically.",
        )
    if is_self_host() and makerspace.frontend_domain_status == Makerspace.DomainStatus.VERIFIED:
        return (makerspace.frontend_domain_status, makerspace.domain_verified_at, "Domain verified.")
    # Platform subdomains are provisioned+verified by staff and have no per-tenant TXT
    # record. Running the custom-domain DNS flow on them would mark them FAILED and drop
    # the live tenant host from the allowlists — so keep them VERIFIED without a lookup.
    if _is_platform_managed(target):
        return _commit_status(
            makerspace,
            target,
            Makerspace.DomainStatus.VERIFIED,
            set_verified_at=True,
            actor=actor,
            detail="Platform-managed subdomain — verified automatically.",
        )

    records = []
    lookup_errors = []
    for prefix in EXPECTED_HOST_PREFIXES:
        try:
            records.extend(_resolve_txt(f"{prefix}.{target}"))
        except Exception as exc:  # A legacy DNS label may be absent during transition.
            lookup_errors.append(exc)

    if not records and lookup_errors:
        return _commit_status(
            makerspace,
            target,
            Makerspace.DomainStatus.FAILED,
            set_verified_at=False,
            actor=actor,
            detail=f"DNS lookup failed: {lookup_errors[0]}",
        )

    if makerspace.domain_verification_token in records:
        if not resolves_to_origin(makerspace):
            return _commit_status(
                makerspace,
                target,
                Makerspace.DomainStatus.FAILED,
                set_verified_at=False,
                actor=actor,
                detail="Domain does not resolve to the platform origin yet.",
            )
        return _commit_status(
            makerspace,
            target,
            Makerspace.DomainStatus.VERIFIED,
            set_verified_at=True,
            actor=actor,
            detail="Domain verified.",
        )

    return _commit_status(
        makerspace,
        target,
        Makerspace.DomainStatus.FAILED,
        set_verified_at=False,
        actor=actor,
        detail="Verification token was not found in DNS TXT records.",
    )
