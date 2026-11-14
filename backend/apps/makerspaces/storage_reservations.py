"""Durable tenant upload admission; all mutations serialize on the makerspace."""
from datetime import timedelta
from functools import wraps

from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone
from django.utils.translation import gettext
from rest_framework.exceptions import ValidationError

from .models import Makerspace
from .models_storage_reservations import StorageQuotaReservation as Reservation

# These are server-minted namespaces. Account imagery has its own global owner;
# it must never interpret a user id as a tenant id.
TENANT_PREFIXES = frozenset({
    "evidence", "items", "machine", "machines", "event", "event-series", "shop",
    "sponsor", "member", "makerspace", "printers", "spaces", "procurement",
    "warranty", "repairs", "card-assets", "card-photos", "member-cards",
})


def reserved_bytes(space, kind=None):
    rows = Reservation.objects.filter(makerspace=space, converted=False, released=False)
    if kind is not None:
        rows = rows.filter(kind=kind)
    return rows.aggregate(n=Sum("size_bytes"))["n"] or 0


@transaction.atomic
def reserve(space_id, key, size, *, bucket, staging_key, ttl, kind="public_image", final_bucket=None):
    from django.conf import settings
    from .limits_uploads import STORAGE_CLASS_KEYS
    from .limits_usage import _storage
    from . import limits
    from apps.managed_hosting.extra_quotas import check_storage_class

    if type(size) is not int or size < 1 or type(ttl) is not int or ttl < 1 or kind not in STORAGE_CLASS_KEYS:
        raise ValueError("Invalid storage quota reservation.")
    space = Makerspace.objects.select_for_update(no_key=True).get(pk=space_id)
    from .limits_uploads import check_upload_size
    check_upload_size(space, size)
    existing = Reservation.objects.filter(object_key=key).first()
    if existing is not None:
        # A fresh signature must not extend an old URL's reconciliation horizon.
        raise ValidationError({"code": "upload_limit", "detail": gettext("Upload not found; upload the photo first.")})
    budget = limits.resource_limit(space, "storage")
    if budget is not None and _storage(space) + size > budget:
        message = gettext("You've reached the free storage limit for this space — ask the operator to raise it or self-host.")
        raise ValidationError({"limit": message, "code": "limit_reached", "detail": message})
    check_storage_class(space, STORAGE_CLASS_KEYS[kind], size)
    return Reservation.objects.create(
        makerspace=space, object_key=key, final_key=key, staging_key=staging_key, bucket=bucket,
        final_bucket=final_bucket or bucket, storage_endpoint=settings.AWS_S3_ENDPOINT_URL or "",
        kind=kind, size_bytes=size, expires_at=timezone.now() + timedelta(seconds=ttl),
    )


def presign_reservation(key, maximum, *, bucket, staged, ttl, final_bucket=None):
    parts = key.split("/")
    if parts[0] == "account":
        return None  # Account-owned images are explicitly outside a tenant budget.
    if len(parts) < 3 or parts[0] not in TENANT_PREFIXES or not parts[1].isdigit():
        raise ValueError("Unknown tenant upload namespace.")
    space = Makerspace.objects.get(pk=int(parts[1]))
    reserve(space.pk, key, maximum, bucket=bucket, staging_key=staged, ttl=ttl,
            kind="evidence" if parts[0] == "evidence" else "public_image", final_bucket=final_bucket)
    return maximum


def cover_authorization(key, ttl):
    """Caller retains admission's transaction/tenant lock through signing."""
    if key.startswith("account/"):
        return
    row = Reservation.objects.select_for_update().get(object_key=key)
    row.expires_at = max(row.expires_at, timezone.now() + timedelta(seconds=ttl))
    row.save(update_fields=["expires_at"])


def reserved_presign(maximum, *, public=False):
    """Wrap legacy and capability transports at the same server-minted key seam."""
    def decorate(function):
        @wraps(function)
        def wrapped(key, content_type, *args, **kwargs):
            from django.conf import settings
            ceiling_args = {name: value for name, value in kwargs.items() if name != "exact_bytes"}
            maximum_bytes = maximum(*args, **ceiling_args) if callable(maximum) else getattr(settings, maximum)
            exact = kwargs.get("exact_bytes")
            if exact is not None:
                if type(exact) is not int or not 1 <= exact <= maximum_bytes:
                    raise ValidationError({"code": "upload_limit", "detail": gettext("Upload exceeds the size limit.")})
                maximum_bytes = exact
            bucket = settings.PUBLIC_IMAGE_BUCKET if public else settings.AWS_STORAGE_BUCKET_NAME
            final_bucket = bucket
            staged = "staging/" + key
            if public and getattr(settings, "STORAGE_CAPABILITIES_FILE", ""):
                bucket = settings.AWS_STORAGE_BUCKET_NAME
                staged = "staging/public-images/" + key
            ttl = settings.PUBLIC_IMAGE_URL_TTL_SECONDS if public else settings.EVIDENCE_URL_TTL_SECONDS
            with transaction.atomic():
                presign_reservation(key, maximum_bytes, bucket=bucket, staged=staged,
                    ttl=ttl, final_bucket=final_bucket)
                upload = function(key, content_type, *args, **kwargs)
                cover_authorization(key, ttl)
                return upload
        return wrapped
    return decorate


def convert(space, key, size, kind, final_key=None):
    """Caller holds the space lock; conversion rolls back with failed attachment."""
    row = Reservation.objects.select_for_update().filter(
        Q(object_key=key) | Q(final_key=key), makerspace=space).first()
    if row is None:
        return  # Pre-migration uploads still use the ordinary finalization charge.
    if row.released or row.cleaning or row.converted or row.kind != kind:
        raise ValidationError({"code": "upload_limit", "detail": gettext("Upload not found; upload the photo first.")})
    row.converted = True
    row.final_key = final_key or row.final_key
    row.save(update_fields=["converted", "final_key"])


@transaction.atomic
def record_final_key(key, final_key):
    """Keep a normalized object's key in the durable debt before writing it."""
    row = Reservation.objects.filter(object_key=key).first()
    if row is None:
        return
    Makerspace.objects.select_for_update(no_key=True).get(pk=row.makerspace_id)
    row = Reservation.objects.select_for_update().get(pk=row.pk)
    if row.cleaning or row.released or row.converted:
        raise ValidationError({"code": "upload_limit", "detail": gettext("Upload not found; upload the photo first.")})
    if row.final_key != row.object_key:
        return row.final_key  # Retry reuses the first durable write claim.
    row.final_key = final_key
    row.save(update_fields=["final_key"])
    return row.final_key


def release(space, key):
    """Only a caller that confirmed removal of both object keys may release debt."""
    with transaction.atomic():
        Makerspace.objects.select_for_update(no_key=True, nowait=True).get(pk=space.pk)
        Reservation.objects.filter(makerspace=space, object_key=key).update(released=True)
