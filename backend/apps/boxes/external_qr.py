"""Register QR labels printed outside SpaceWorks against inventory (owner request).

An external label becomes an ordinary `QrCode` row with `source=external`: scans, revoke,
scan-history immutability and active-target uniqueness are the ones every QR has. Rules:

* the value is trimmed, case preserved, at most 64 printable characters;
* unique per makerspace across EVERY status (a revoked label never re-links), the same
  value in another makerspace is a different, invisible label;
* an assigned value is never reassigned -- the caller gets the linked item back;
* a target that already has an active QR keeps it; revoke that first.
"""
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext
from rest_framework.exceptions import APIException, ValidationError

from apps.audit import services as audit
from apps.boxes.models import QrCode
from apps.boxes.qr_lookup import EXTERNAL_VALUE_MAX_LENGTH, normalize_scanned, scanned_q
from apps.inventory.models import InventoryAsset, InventoryProduct, TrackingMode

ALREADY_ASSIGNED = "already_assigned"
REVOKED = "revoked"
TARGET_HAS_QR = "target_has_qr"


class ExternalQrConflict(APIException):
    status_code = 409

    def __init__(self, code, detail, *, qr=None, target=None):
        super().__init__(detail, code=code)
        body = {"code": code, "detail": str(detail)}
        if qr is not None:
            body["qr_id"] = qr.id
        if target is not None:
            body["target"] = target
        self.detail = body


def value_error(value):
    """Why `value` cannot be an external label, or None. `value` is already normalized."""
    if not value:
        return gettext("Scan or enter the QR code value.")
    if len(value) > EXTERNAL_VALUE_MAX_LENGTH:
        return gettext("QR code values can be at most 64 characters.")
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        return gettext("QR code values cannot contain control characters.")
    return None


def clean_value(value):
    value = normalize_scanned(value)
    error = value_error(value)
    if error:
        raise ValidationError({"value": [error]})
    return value


def value_holder(makerspace_id, value):
    """The QR in this makerspace that already owns `value` (active first), or None."""
    return (
        QrCode.objects.filter(makerspace_id=makerspace_id)
        .filter(scanned_q(value))
        .order_by("status", "id")
        .first()
    )


def is_foreign_payload(makerspace_id, value):
    """A SpaceWorks payload is deployment-unique: one printed for another makerspace must
    never become this makerspace's external label too (one sticker, two items)."""
    return QrCode.objects.filter(payload=value).exclude(makerspace_id=makerspace_id).exists()


def active_qr_for(makerspace_id, target_type, target_id):
    return QrCode.objects.filter(
        makerspace_id=makerspace_id, target_type=target_type,
        target_id=target_id, status=QrCode.Status.ACTIVE,
    ).first()


def holder_conflict_code(holder, target_type, target_id):
    """None when `holder` already IS this assignment (idempotent re-link)."""
    if holder.status == QrCode.Status.REVOKED:
        return REVOKED
    if holder.target_type == target_type and holder.target_id == target_id:
        return None
    return ALREADY_ASSIGNED


def conflict_for(holder, code):
    from apps.boxes.serializers import qr_target_payload

    if code == REVOKED:
        return ExternalQrConflict(code, gettext(
            "This QR code was revoked in this makerspace and cannot be linked again."), qr=holder)
    if code == TARGET_HAS_QR:
        return ExternalQrConflict(code, gettext(
            "This item already has an active QR code. Revoke it before linking another."), qr=holder)
    target = None
    if holder.target_type != QrCode.TargetType.MEMBER_CARD:
        target = qr_target_payload(holder)
    return ExternalQrConflict(code, gettext(
        "This QR code is already linked. The existing link was kept."), qr=holder, target=target)


def target_for(makerspace, *, product_id=None, asset_id=None):
    if asset_id:
        asset = get_object_or_404(InventoryAsset, pk=asset_id, makerspace=makerspace)
        return QrCode.TargetType.ASSET, asset
    product = get_object_or_404(InventoryProduct, pk=product_id, makerspace=makerspace)
    if product.tracking_mode == TrackingMode.INDIVIDUAL:
        raise ValidationError(gettext("Individual-tracked inventory requires unit QR codes."))
    return QrCode.TargetType.PRODUCT, product


def assign_external_qr(actor, makerspace, value, target_type, target, *, source):
    """Link `value` to `target`. Returns (qr, created); raises ExternalQrConflict."""
    value = clean_value(value)
    with transaction.atomic():
        holder = value_holder(makerspace.id, value)
        if holder is not None:
            code = holder_conflict_code(holder, target_type, target.id)
            if code is None:
                return holder, False
            raise conflict_for(holder, code)
        if is_foreign_payload(makerspace.id, value):
            raise ExternalQrConflict(ALREADY_ASSIGNED, gettext(
                "This is a SpaceWorks label from another makerspace and cannot be linked here."))
        existing = active_qr_for(makerspace.id, target_type, target.id)
        if existing is not None:
            raise conflict_for(existing, TARGET_HAS_QR)
        try:
            with transaction.atomic():
                qr = QrCode.objects.create(
                    makerspace=makerspace, source=QrCode.Source.EXTERNAL, external_value=value,
                    target_type=target_type, target_id=target.id, created_by=actor,
                )
        except IntegrityError:
            # Lost a race: report whoever won, never overwrite it.
            holder = value_holder(makerspace.id, value)
            if holder is not None:
                raise conflict_for(holder, holder_conflict_code(holder, None, None))
            raise conflict_for(active_qr_for(makerspace.id, target_type, target.id), TARGET_HAS_QR)
        audit.record(
            actor, "qr.external_assigned", makerspace=makerspace, target=target,
            meta={"qr_id": qr.id, "target_type": target_type, "source": source},
        )
    return qr, True
