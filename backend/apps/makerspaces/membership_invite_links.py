"""Shareable membership invite links: create, list, revoke, redeem (X11).

Staff with MANAGE_MEMBERS create a link (optional label, plan, use limit, expiry) and see
its clear code exactly once. Redeeming happens inside the join request's makerspace lock:
the link row is locked, checked (not revoked, not expired, uses left) and its use count
bumped in the same transaction as the request it admits, so a link can never be used
more times than its limit however many people click at once.
"""
from django.utils.translation import gettext
import hashlib
import hmac
import secrets

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound, ValidationError

from apps.audit import services as audit
from apps.makerspaces.models import MembershipInviteLink, MembershipPlan

MAX_USES = 10000


def code_digest(code):
    message = f"membership-invite:{str(code or '').strip()}".encode()
    return hmac.new(settings.SECRET_KEY.encode(), message, hashlib.sha256).hexdigest()


def create_link(actor, makerspace, *, label="", plan_id=None, max_uses=1, expires_at=None):
    if not 1 <= int(max_uses) <= MAX_USES:
        raise ValidationError({"max_uses": gettext('Use a limit between 1 and {MAX_USES}.').format(MAX_USES=MAX_USES)})
    if expires_at is not None and expires_at <= timezone.now():
        raise ValidationError({"expires_at": gettext("Choose a time in the future.")})
    plan = None
    if plan_id is not None:
        plan = MembershipPlan.objects.filter(makerspace=makerspace, pk=plan_id, is_active=True,
                                             archived_at__isnull=True).first()
        if plan is None:
            raise ValidationError({"plan_id": gettext("Choose an active plan in this makerspace.")})
    code = secrets.token_urlsafe(18)
    with transaction.atomic():
        from apps.tenant_migration.gate_runtime import assert_write_allowed
        assert_write_allowed(makerspace.pk)
        link = MembershipInviteLink.objects.create(
            makerspace=makerspace, code_digest=code_digest(code), label=(label or "")[:120], plan=plan,
            max_uses=int(max_uses), expires_at=expires_at, created_by=actor,
        )
        audit.record(actor, "membership.invite_link_created", makerspace=makerspace, target=link,
                     meta={"link_id": link.pk, "plan_id": plan.pk if plan else None, "max_uses": link.max_uses})
    return link, code


def revoke_link(actor, link):
    with transaction.atomic():
        link = MembershipInviteLink.objects.select_for_update().get(pk=link.pk)
        if link.revoked_at is None:
            link.revoked_at = timezone.now()
            link.save(update_fields=["revoked_at"])
            audit.record(actor, "membership.invite_link_revoked", makerspace=link.makerspace, target=link,
                         meta={"link_id": link.pk, "uses": link.uses})
    return link


def peek(makerspace, code):
    """The live link for `code` without consuming it (the join page shows its plan)."""
    link = MembershipInviteLink.objects.select_related("plan").filter(
        makerspace=makerspace, code_digest=code_digest(code)).first()
    if link is None or not link.live(timezone.now()):
        raise NotFound(gettext("This invite link is not valid."))
    return link


def redeem_locked(makerspace, code, *, actor):
    """Consume one use. The caller holds the makerspace lock and an open transaction."""
    link = MembershipInviteLink.objects.select_for_update().filter(
        makerspace=makerspace, code_digest=code_digest(code)).first()
    if link is None or not link.live(timezone.now()):
        raise NotFound(gettext("This invite link is not valid."))
    link.uses += 1
    link.save(update_fields=["uses"])
    audit.record(actor, "membership.invite_link_redeemed", makerspace=makerspace, target=link,
                 meta={"link_id": link.pk, "uses": link.uses})
    return link
