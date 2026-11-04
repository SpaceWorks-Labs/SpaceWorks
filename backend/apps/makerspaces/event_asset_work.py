"""Bounded event object plans and idempotent storage work, without domain locks."""

from pathlib import PurePosixPath
from uuid import uuid4

from django.db import transaction
from rest_framework.exceptions import ValidationError

from apps.evidence.storage import StorageUnavailable
from . import website_assets
from .event_asset_transaction import InspectImage
from .website_asset_journal import reserve


def _plan(copies, signature, page, key, size, **work):
    def reservation():
        if len(copies.plans) >= copies.maximum or copies.total_bytes + size > copies.max_total_bytes:
            raise ValidationError("The clone asset limit was exceeded.")
        job_id = reserve(page, key, size, copies)
        copies.total_bytes += size
        return dict(signature=signature, page=page, key=key, size=size,
                    job_id=job_id, ready=False, **work)
    return copies.step(signature, reservation, page=page)


def plan_copy(copies, makerspace, image, *, storage, page, expected_size):
    if not image.source_key:
        return ""
    if (page is None or page.makerspace_id != makerspace.pk
            or not image.source_prefix.endswith("/")
            or not image.destination_prefix.endswith("/")
            or not image.source_key.startswith(image.source_prefix)
            or not storage.is_safe_object_key(image.source_key)
            or not storage.is_safe_object_key(image.destination_prefix)):
        raise ValidationError("Image is not owned by the source resource.")
    if expected_size is None:
        if image.source_key not in copies.sizes:
            raise InspectImage(storage, image.source_key)
        expected_size = copies.sizes[image.source_key]
    if expected_size is None or not 0 < expected_size <= image.max_bytes:
        raise ValidationError("The source image is missing or too large.")
    signature = ("copy", image.source_key, image.destination_prefix, expected_size)
    key = image.destination_prefix + uuid4().hex + PurePosixPath(image.source_key).suffix
    plan = _plan(copies, signature, page, key, expected_size,
                 storage=storage, source=image.source_key)
    return plan["key"]


def plan_upload(copies, file, page):
    if id(file) not in copies.uploads:
        data = file.read(website_assets.MAX_BYTES + 1)
        copies.uploads[id(file)] = (data, website_assets.webp(data))
    data, converted = copies.uploads[id(file)]
    key = website_assets.prefix("events", page.makerspace_id, page.pk) + uuid4().hex + ".webp"
    signature = ("upload", page.pk, id(file))
    plan = _plan(copies, signature, page, key, len(converted),
                 storage=website_assets, data=data, converted=converted)
    return plan["key"], plan["size"]


def perform(plan):
    """A repeated attempt never replaces an already verified destination key."""
    if transaction.get_connection().in_atomic_block:
        raise RuntimeError("Object work must run outside database transactions.")
    storage, key, size = plan["storage"], plan["key"], plan["size"]
    existing = storage.object_size(key)
    if existing is not None and existing != size:
        raise StorageUnavailable("Reserved image verification failed.")
    if existing is None:
        if "source" in plan:
            if storage.object_size(plan["source"]) != size:
                raise ValidationError("The source image metadata does not match its bytes.")
            storage.copy_object(plan["source"], key)
        else:
            storage._put("staging/" + key, plan["data"], "application/octet-stream")
            storage._put(key, plan["converted"], "image/webp")
        if storage.object_size(key) != size:
            raise StorageUnavailable("Reserved image verification failed.")
    if "source" not in plan and storage.delete_object("staging/" + key) is not True:
        raise StorageUnavailable("Staging deletion was not confirmed.")
    plan["ready"] = True
