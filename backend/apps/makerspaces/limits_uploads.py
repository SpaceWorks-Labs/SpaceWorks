"""Upload caps from the effective limits (#234 addendum 2): one file's size and the storage budget.

Two seams, both no-ops when the space has no limit (nothing set; own and self-host spaces included):

* ``check_upload_headroom`` at PRESIGN: refuse before the browser uploads anything when the
  storage budget is already spent, or when a declared size is over the per-file cap.
  The storage presigner also acquires durable debt through ``storage_reservations``.
* ``charge_upload`` at FINALIZE: convert the key's reservation in the attachment transaction;
  the real object size must fit both class and combined budgets before ``add_storage``.

Only member/staff UPLOADS use these. Server-made objects (exports, restores, rendered cards,
certificate reservations) keep calling ``add_storage`` directly: a per-file cap is about what a
person may upload, not about what the platform writes for them.
"""

from django.utils.translation import gettext
from django.db import transaction
from rest_framework import serializers


def _mib(size_bytes):
    return f"{size_bytes / 1024 ** 2:.1f} MB"


def _refuse(message):
    raise serializers.ValidationError({"limit": message, "detail": message, "code": "upload_limit"}, code="limit_reached")


def upload_cap(makerspace):
    """The largest single upload this space accepts, in bytes, or None (no cap)."""
    from apps.makerspaces import limits

    return limits.resource_limit(makerspace, "upload_bytes")


def check_upload_size(makerspace, size_bytes):
    cap = upload_cap(makerspace)
    if cap is not None and size_bytes and size_bytes > cap:
        _refuse(gettext("This file is {size}; files here can be at most {cap}.").format(
            size=_mib(size_bytes), cap=_mib(cap)))


def check_upload_headroom(makerspace, size_bytes=None):
    """Presign-time check. ``size_bytes`` is the declared size when the client sends one."""
    from apps.makerspaces import limits
    from apps.makerspaces.limits_usage import _storage

    # No self-host early return (#261): a limit the superadmin SET applies to every space, and
    # ``resource_limit`` already answers None (no check) when nothing is set.
    if size_bytes:
        check_upload_size(makerspace, size_bytes)
    budget = limits.resource_limit(makerspace, "storage")
    if budget is None:
        return
    used = _storage(makerspace)
    if used >= budget or (size_bytes and used + size_bytes > budget):
        _refuse(gettext("This space has used its {budget} of storage. Remove old files or ask the "
                        "platform operator for more room.").format(budget=_mib(budget)))


STORAGE_CLASS_KEYS = {"evidence": "storage_evidence_bytes", "public_image": "storage_public_images_bytes"}


@transaction.atomic
def charge_upload(makerspace, size_bytes, kind="public_image", *, object_key=None, final_key=None):
    """Finalize-time: per-file cap, then the storage class's own limit, then the locked storage charge.

    ``kind`` picks the split byte limit (decision 284 addendum): ``evidence`` for evidence photos,
    ``public_image`` (the default) for everything else a person uploads. The combined ``storage``
    key keeps working underneath both; every limit is "none" unless the superadmin set it.

    Looks ``add_storage`` up on the ``limits`` barrel at call time, so the existing seam (and
    every test that replaces ``apps.makerspaces.limits.add_storage``) keeps working.
    """
    from apps.makerspaces import limits
    from apps.makerspaces.models import Makerspace

    # Refresh usage under the creators' shared lock before checking either class.
    # A caller can finalize multiple uploads using the same stale space instance.
    makerspace = Makerspace.objects.select_for_update(no_key=True).get(pk=makerspace.pk)
    check_upload_size(makerspace, size_bytes)
    if object_key:
        from .storage_reservations import convert
        convert(makerspace, object_key, size_bytes, kind, final_key)
    from apps.managed_hosting.extra_quotas import check_storage_class
    check_storage_class(makerspace, STORAGE_CLASS_KEYS[kind], size_bytes)
    limits.add_storage(makerspace, size_bytes)
