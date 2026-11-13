"""Issue, update and void wallet passes (#132, #133): every network step is a job.

Issue: the holder asks; a `wallet_issue` job builds the pass (Apple .pkpass object or a
Google save link) and the holder downloads it. Update: reissue, revoke and design or
data changes queue a `wallet_update` job; a periodic sweep also catches renewals and
expiries by comparing each pass's content digest. A revoked card's pass is voided.
"""
from django.utils.translation import gettext
import logging
import secrets

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.audit import services as audit

from ..models import CardJob, WalletPass
from .content import content_digest, pass_content
from .credentials import apple_for, auth_token, configured_platforms, digest

logger = logging.getLogger(__name__)
SCOPES = {"member_card": "member_cards", "programme_card": "id_programme", "event_card": "event",
          "staff_card": "staff_cards"}


def _check_platform_allowance(kind, card, platform):
    """Owner 2026-11-11: a NEW pass signed with the PLATFORM certificates counts against the space's monthly
    allowance (null = unlimited). Own-credential passes and re-requests of an existing pass are never limited."""
    from apps.managed_hosting.platform_limits import note_reached, platform_limit, platform_refusal
    from .credentials import apple_for, google_for
    space = card.makerspace
    if platform_limit(space, "platform_wallet_monthly") is None or WalletPass.objects.filter(
            **{kind: card}, platform=platform).exists():
        return
    creds = apple_for(space.pk) if platform == "apple" else google_for(space.pk)
    if creds is None or getattr(creds, "source", "") != "platform":
        return
    refusal = platform_refusal(space, "platform_wallet_monthly")
    if refusal:
        note_reached(space, "platform_wallet_monthly")
        raise ValidationError({"platform": refusal, "code": "platform_wallet_limit_reached"},
                              code="platform_wallet_limit_reached")


def request_pass(actor, kind, card, platform):
    from ..jobs import enqueue
    from ..switches import wallet_on
    if platform not in configured_platforms(card.makerspace_id) or not wallet_on(kind, card.makerspace):
        raise ValidationError({"platform": gettext("Wallet passes are not available here.")})
    _check_platform_allowance(kind, card, platform)
    if not WalletPass.objects.filter(**{kind: card}, platform=platform).exists():
        from apps.managed_hosting.extra_quotas import check_extra_quota
        check_extra_quota(card.makerspace, "wallet_passes")  # decision 284: only a NEW pass counts
    with transaction.atomic():
        row, created = WalletPass.objects.get_or_create(
            **{kind: card}, platform=platform,
            defaults={"makerspace_id": card.makerspace_id, "serial": secrets.token_hex(16), "auth_token_digest": ""})
        if created:
            row.auth_token_digest = digest(auth_token(row.serial))
            creds = apple_for(card.makerspace_id) if platform == "apple" else None
            row.pass_type_id = creds.pass_type_id if creds else ""
            row.save(update_fields=["auth_token_digest", "pass_type_id"])
        job, _ = enqueue(actor, card.makerspace, CardJob.Kind.WALLET_ISSUE, scope=SCOPES[kind], targets=[card.pk],
                         params={}, revision=f"{platform}:{row.serial}:{row.generation}")
        CardJob.objects.filter(pk=job.pk).update(params={"platform": platform, "pass_id": row.pk})
    return row, job


def issue_from_job(job):
    from apps.tenant_migration.gate_runtime import assert_write_allowed
    assert_write_allowed(job.makerspace_id)
    from ..jobs import holder_kind
    from ..storage import put_bytes
    row = WalletPass.objects.filter(pk=(job.params or {}).get("pass_id")).first()
    if row is None:
        return False
    kind = holder_kind(job)
    card = getattr(row, kind)
    from ..switches import wallet_on
    if not wallet_on(kind, card.makerspace):
        return False  # decision 329: switched off after the request, so no new pass is built
    content = pass_content(kind, card)
    if row.platform == "apple":
        from .apple import build_pkpass
        key = f"card-jobs/{job.makerspace_id}/{job.pk}/pass.pkpass"
        put_bytes(key, build_pkpass(row, content), "application/vnd.apple.pkpass")
        job.parts = [key]
    else:
        from .google import save_link
        job.params = {**job.params, "save_url": save_link(row, content)}
        CardJob.objects.filter(pk=job.pk).update(params=job.params)
    WalletPass.objects.filter(pk=row.pk).update(last_updated_at=timezone.now(), content_digest=content_digest(content))
    from .credentials import google_for
    creds = apple_for(job.makerspace_id) if row.platform == "apple" else google_for(job.makerspace_id)
    # `source` ("platform" when signed with the operator's certificates) is what `platform_wallet_monthly`
    # counts: only platform-signed passes, never a space's own certificates.
    audit.record(job.requested_by, "wallet_pass.issued", makerspace=job.makerspace, target=row,
                 meta={"pass_id": row.pk, "platform": row.platform, "source": getattr(creds, "source", "own")})
    return True


# Decision 329 (a): with the kind's wallet switch off, an existing pass still hears that it ended
# (voided, revoked or expired), so a revoked card never looks valid; nothing else changes on it.
ENDED = frozenset({"revoked", "expired"})


def update_allowed(kind, card, row, content):
    from apps.makerspaces.platform import feature_enabled
    from ..switches import WALLET
    return bool(row.voided_at) or content["standing"] in ENDED or feature_enabled(card.makerspace, WALLET[kind])


def refresh(kind, card):
    """Push current content to every pass of this card; voided passes get a final update."""
    changed = 0
    for row in WalletPass.objects.filter(**{kind: card}):
        content = pass_content(kind, card)
        if not update_allowed(kind, card, row, content):
            continue  # switched off: no content change; the sweep sends it if the switch comes back
        try:
            if row.platform == "apple":
                from .apple_push import notify
                notify(row)
            else:
                from .google import push_update
                push_update(row, content)
        except Exception:
            logger.warning("wallet_pass_update_failed", extra={"pass_id": row.pk})
            continue
        WalletPass.objects.filter(pk=row.pk).update(generation=row.generation + 1, last_updated_at=timezone.now(),
                                                    content_digest=content_digest(content))
        if row.voided_at:
            audit.record(None, "wallet_pass.voided", makerspace=row.makerspace, target=row,
                         meta={"pass_id": row.pk, "platform": row.platform})
        else:
            audit.record(None, "wallet_pass.updated", makerspace=row.makerspace, target=row,
                         meta={"pass_id": row.pk, "platform": row.platform})
        changed += 1
    return changed


def enqueue_update(kind, card_id):
    from ..holders import registered
    from ..jobs import enqueue
    spec = registered().get(kind)
    card = spec.model().objects.filter(pk=card_id).first() if spec else None
    if card is None:
        return None
    job, _ = enqueue(None, card.makerspace, CardJob.Kind.WALLET_UPDATE, scope=SCOPES[kind], targets=[card_id],
                     params={}, revision=timezone.now().isoformat())
    return job


def sweep_changed(*, limit=100):
    """Refresh passes whose content changed (renewals, expiry) since they were last sent."""
    from ..switches import live_holder_q
    # A pass is refreshed only while its card kind is on (#183B); with the wallet switch off only an
    # ending (revoked/expired) reaches it (decision 329).
    rows = WalletPass.objects.filter(live_holder_q(), voided_at__isnull=True).order_by("last_updated_at")[:limit]
    refreshed = 0
    for row in rows:
        kind = row.holder_kind
        card = getattr(row, kind)
        content = pass_content(kind, card)
        current = content_digest(content)
        if not update_allowed(kind, card, row, content):
            WalletPass.objects.filter(pk=row.pk).update(last_updated_at=timezone.now())  # rotate the bounded batch
        elif row.content_digest and row.content_digest != current:
            refreshed += refresh(kind, card)
        elif not row.content_digest:
            WalletPass.objects.filter(pk=row.pk).update(content_digest=current, last_updated_at=timezone.now())
        else:
            WalletPass.objects.filter(pk=row.pk).update(last_updated_at=timezone.now())
    return refreshed
