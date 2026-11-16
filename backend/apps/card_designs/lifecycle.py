"""What every holder kind does on issue, reissue, renewal and revoke (SPEC §5.1).

Called INSIDE the owning service's transaction, so the token, wallet and extras
changes commit or roll back with the card. Wallet updates are queued jobs and never
block the card itself.
"""
from django.db import transaction
from django.utils import timezone

from . import tokens
from .models import CardHolderExtras, CardPhotoRequest, CardVerifyToken, WalletPass


def public_verify_on(kind, card):
    from .holders import registered
    spec = registered().get(kind)
    return bool(spec and spec.public_verify(card))


def on_issue(kind, card):
    if public_verify_on(kind, card):
        tokens.mint(kind, card)


def on_reissue(kind, card):
    """The old printed card now verifies as revoked ("A newer card was issued")."""
    tokens.retire(kind, card, CardVerifyToken.Retired.REISSUED)
    if public_verify_on(kind, card):
        tokens.mint(kind, card)
    queue_wallet_update(kind, card)


def on_renew(kind, card):
    """Same card, number and QR; only the valid-until moves, so passes are refreshed."""
    queue_wallet_update(kind, card)


def on_revoke(kind, card):
    tokens.retire(kind, card, CardVerifyToken.Retired.REVOKED)
    CardHolderExtras.objects.filter(**{kind: card}).delete()
    CardPhotoRequest.objects.filter(**{kind: card}, resolved_at__isnull=True).update(resolved_at=timezone.now())
    passes = list(WalletPass.objects.filter(**{kind: card}, voided_at__isnull=True))
    if passes:
        WalletPass.objects.filter(pk__in=[row.pk for row in passes]).update(voided_at=timezone.now())
        queue_wallet_update(kind, card, force=True)


def queue_wallet_update(kind, card, *, force=False):
    if not force and not WalletPass.objects.filter(**{kind: card}, voided_at__isnull=True).exists():
        return
    from .wallet.service import enqueue_update
    transaction.on_commit(lambda: enqueue_update(kind, card.pk), robust=True)
