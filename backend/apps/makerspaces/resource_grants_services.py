"""Audited, locked grant lifecycle, parameterised by a typed domain adapter."""

from django.utils.translation import gettext
import hashlib
import hmac
import secrets
from dataclasses import dataclass
from typing import Callable, Literal, Protocol

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist, ValidationError as ModelValidationError
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from apps.audit.services import record
from .resource_grants_models import validate_permission_set


class GrantSubsetValidator(Protocol):
    def __call__(
        self, *, actor: object, target: object, permissions: tuple[str, ...],
        operation: Literal["create_invite", "update_permissions", "revoke_grant",
                           "revoke_invite", "redeem_invite"], row: object | None,
    ) -> bool:
        """Explicit True permits the complete subset/scope; anything else denies."""
        ...


@dataclass(frozen=True)
class GrantAdapter:
    grant_model: type
    invite_model: type
    permissions: tuple
    namespace: str
    audit_prefix: str
    target: Callable
    lock_target: Callable
    scope: Callable
    can_manage: Callable
    can: Callable
    active: Callable
    lock_authority: Callable
    # Optional display-only label column (events' role_label). Never consulted for authority.
    label_field: str | None = None
    # Opt-in Events helper policy. Bookings retains its full-manager-only default.
    # Called under authority locks for issue/update/revoke AND redemption.
    subset_validator: GrantSubsetValidator | None = None
    grant_written: Callable | None = None


def credential_digest(value, *, namespace, purpose):
    # Bearer tokens are case-sensitive. Only email identity is normalized.
    normalized = str(value).strip().lower() if purpose == "email" else str(value)
    message = f"resource-grants:{namespace}:{purpose}:{normalized}".encode()
    return hmac.new(settings.SECRET_KEY.encode(), message, hashlib.sha256).hexdigest()


def _permissions(adapter, values):
    try:
        validate_permission_set(values, adapter.permissions)
    except ModelValidationError as exc:
        raise ValidationError({"permissions": exc.messages}) from exc
    return sorted(values)


def _require_subset(
    adapter, actor, target, permissions, *, operation="create_invite", row=None,
    authority_locked=False,
):
    if not authority_locked:
        actor = adapter.lock_authority(actor, target)
    if adapter.subset_validator is not None:
        if not adapter.active(actor):
            raise PermissionDenied(gettext("An active account is required."))
        allowed = adapter.subset_validator(
            actor=actor, target=target, permissions=tuple(permissions),
            operation=operation, row=row,
        )
        # The domain validator decides delegation scope; every requested permission is
        # still revalidated through the adapter so the two can never drift apart.
        if allowed is not True or not all(adapter.can(actor, target, p) for p in permissions):
            raise PermissionDenied(gettext("Resource staff access cannot exceed current authority."))
        return actor
    if not adapter.can_manage(actor, target) or not all(
        adapter.can(actor, target, permission) for permission in permissions
    ):
        raise PermissionDenied(gettext("Resource staff access cannot exceed current authority."))
    return actor


def _audit(adapter, actor, action, row):
    meta = {"permissions": row.permissions}
    if adapter.label_field and getattr(row, adapter.label_field):
        meta[adapter.label_field] = getattr(row, adapter.label_field)
    record(actor, f"{adapter.audit_prefix}_{action}", makerspace=row.makerspace,
           target=row, meta=meta)


def _labels(adapter, label):
    return {adapter.label_field: label} if adapter.label_field and label is not None else {}


@transaction.atomic
def create_invite(adapter, target, *, actor, permissions, email="", send=None, label=None):
    target = adapter.lock_target(target)
    permissions = _permissions(adapter, permissions)
    _require_subset(adapter, actor, target, permissions, operation="create_invite")
    if send is not None and not email:
        raise ValidationError({"email": gettext("An email address is required for delivery.")})
    token = secrets.token_urlsafe(32)
    row = adapter.invite_model.objects.create(
        **adapter.scope(target), permissions=permissions, created_by=actor, **_labels(adapter, label),
        token_digest=credential_digest(token, namespace=adapter.namespace, purpose="invite"),
        email_digest=(credential_digest(email, namespace=adapter.namespace, purpose="email")
                      if email else ""),
    )
    _audit(adapter, actor, "invited", row)
    if send is not None:
        transaction.on_commit(lambda: send(row, email, token))
    return row, token


@transaction.atomic
def update_permissions(adapter, grant, *, actor, permissions, label=None):
    target = adapter.lock_target(adapter.target(grant))
    actor = adapter.lock_authority(actor, target)
    row = adapter.grant_model.objects.select_for_update().get(pk=grant.pk)
    if row.revoked_at:
        raise ValidationError({"detail": gettext("This staff grant has been revoked.")})
    permissions = _permissions(adapter, permissions)
    _require_subset(adapter, actor, target, permissions, operation="update_permissions",
                    row=row, authority_locked=True)
    row.permissions = permissions
    labels = _labels(adapter, label)
    for field, value in labels.items():
        setattr(row, field, value)
    row.save(update_fields=["permissions", *labels])
    if adapter.grant_written:
        adapter.grant_written(grant=row, permissions=permissions, actor=actor, operation="update_permissions")
    _audit(adapter, actor, "updated", row)
    return row


@transaction.atomic
def revoke_grant(adapter, grant, *, actor):
    target = adapter.lock_target(adapter.target(grant))
    actor = adapter.lock_authority(actor, target)
    row = adapter.grant_model.objects.select_for_update().get(pk=grant.pk)
    _require_subset(adapter, actor, target, (), operation="revoke_grant", row=row,
                    authority_locked=True)
    if row.revoked_at is None:
        row.revoked_at, row.revoked_by = timezone.now(), actor
        row.save(update_fields=["revoked_at", "revoked_by"])
        _audit(adapter, actor, "revoked", row)
    return row


@transaction.atomic
def revoke_invite(adapter, invite, *, actor):
    target = adapter.lock_target(adapter.target(invite))
    actor = adapter.lock_authority(actor, target)
    row = adapter.invite_model.objects.select_for_update().get(pk=invite.pk)
    _require_subset(adapter, actor, target, (), operation="revoke_invite", row=row,
                    authority_locked=True)
    if row.revoked_at is None:
        row.revoked_at = timezone.now()
        row.save(update_fields=["revoked_at"])
        _audit(adapter, actor, "invite_revoked", row)
    return row


@transaction.atomic
def redeem_invite(adapter, token, *, actor, makerspace_id=None):
    if not adapter.active(actor):
        raise PermissionDenied()
    candidate = adapter.invite_model.objects.filter(
        token_digest=credential_digest(token, namespace=adapter.namespace, purpose="invite"),
    ).first()
    if not candidate or (makerspace_id is not None and candidate.makerspace_id != makerspace_id):
        raise NotFound(gettext("Invitation not found."))
    # Domain lock order precedes credentials. No nullable joins under FOR UPDATE.
    from apps.accounts.models import User
    try:
        target = adapter.lock_target(adapter.target(candidate))
        creator = User.objects.filter(pk=candidate.created_by_id).first()
        creator = adapter.lock_authority(creator, target)
        row = adapter.invite_model.objects.select_for_update().get(pk=candidate.pk)
    except ObjectDoesNotExist as exc:
        # A draft occurrence and its cascading invite can disappear during regeneration.
        raise NotFound(gettext("Invitation not found.")) from exc
    if (row.revoked_at or row.redeemed_at or row.expires_at <= timezone.now()
            or row.makerspace_id != target.makerspace_id):
        raise NotFound(gettext("Invitation not found."))
    creator = _require_subset(
        adapter, creator, target, _permissions(adapter, row.permissions),
        operation="redeem_invite", row=row, authority_locked=True,
    )
    account = User.objects.filter(pk=actor.pk).first()
    if not adapter.active(account):
        raise PermissionDenied()
    if row.email_digest and (
        not account.email_verified_at or not account.email or not hmac.compare_digest(
            row.email_digest,
            credential_digest(account.email, namespace=adapter.namespace, purpose="email"),
        )
    ):
        raise PermissionDenied(gettext("A matching verified email is required."))
    grant = adapter.grant_model.objects.select_for_update().filter(
        **adapter.scope(target), user=account, revoked_at__isnull=True,
    ).first()
    if grant is None:
        grant = adapter.grant_model.objects.create(
            **adapter.scope(target), user=account, permissions=row.permissions, granted_by=creator,
            **_labels(adapter, getattr(row, adapter.label_field or "", None)),
        )
        _audit(adapter, actor, "created", grant)
    else:
        grant.permissions = sorted(set(grant.permissions) | set(row.permissions))
        # A merged invitation only fills a missing label; it never relabels a person.
        labels = {} if not adapter.label_field or getattr(grant, adapter.label_field) else _labels(
            adapter, getattr(row, adapter.label_field))
        for field, value in labels.items():
            setattr(grant, field, value)
        grant.save(update_fields=["permissions", *labels])
        _audit(adapter, actor, "updated", grant)
    row.redeemed_at, row.redeemed_by = timezone.now(), account
    row.save(update_fields=["redeemed_at", "redeemed_by"])
    _audit(adapter, actor, "invite_redeemed", row)
    if adapter.grant_written:
        adapter.grant_written(grant=grant, permissions=row.permissions, actor=creator, operation="redeem_invite")
    return grant
