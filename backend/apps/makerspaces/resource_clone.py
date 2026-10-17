"""Owned asset copies for domain clone adapters; never traverse relations implicitly."""

from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass
import logging
from pathlib import PurePosixPath
from uuid import uuid4

from django.db import transaction
from rest_framework.exceptions import ValidationError

from apps.evidence.storage import StorageUnavailable
from apps.makerspaces import limits

logger = logging.getLogger(__name__)


def copy_fields(source, fields):
    """The adapter's explicit allow-list is also the clone's retention boundary."""
    return {field: deepcopy(getattr(source, field)) for field in fields}


def bounded_children(queryset, *, maximum=100):
    rows = list(queryset[:maximum + 1])
    if len(rows) > maximum:
        raise ValidationError("Too many children to duplicate in one operation.")
    return rows


@dataclass(frozen=True)
class OwnedImage:
    source_key: str
    source_prefix: str
    destination_prefix: str
    max_bytes: int


class AssetCopies:
    def __init__(self, *, maximum=100, max_total_bytes=100_000_000):
        self.maximum = maximum
        self.max_total_bytes = max_total_bytes
        self.total_bytes = 0
        self.created = []
        self.committed = False
        self.journal_ids = []
        self.journal_keys = set()

    def copy_image(self, makerspace, image, *, storage, journal_page=None):
        if not image.source_key:
            return ""
        if (not image.source_prefix.endswith("/")
                or not image.destination_prefix.endswith("/")
                or not image.source_key.startswith(image.source_prefix)
                or not storage.is_safe_object_key(image.source_key)
                or not storage.is_safe_object_key(image.destination_prefix)):
            raise ValidationError("Image is not owned by the source resource.")
        size = storage.object_size(image.source_key)
        if size is None or not 0 < size <= image.max_bytes:
            raise ValidationError("The source image is missing or too large.")
        if len(self.created) >= self.maximum or self.total_bytes + size > self.max_total_bytes:
            raise ValidationError("The clone asset limit was exceeded.")
        key = image.destination_prefix + uuid4().hex + PurePosixPath(image.source_key).suffix
        limits.add_storage(makerspace, size)
        if journal_page is not None:
            from .website_asset_journal import enlist
            enlist(journal_page, key, size, self)
        # Enlist before I/O: a timed-out copy may still have created an object.
        self.created.append((storage, key))
        self.total_bytes += size
        storage.copy_object(image.source_key, key)
        if storage.object_size(key) != size:
            raise StorageUnavailable("Copied image verification failed.")
        return key

    def cleanup(self):
        if self.journal_ids:
            from .models_page_cleanup import PublicPageObjectCleanup as Cleanup
            from .public_page_asset_cleanup import clean_object
            from django.utils import timezone
            try:
                Cleanup.objects.filter(pk__in=self.journal_ids).update(due_at=timezone.now())
            except Exception:
                logger.exception("clone_journal_retry_schedule_failed")
            for job_id in self.journal_ids:
                try:
                    clean_object(job_id)
                except Exception:
                    logger.exception("clone_journal_cleanup_failed", extra={"cleanup_id": job_id})
        for storage, key in reversed(self.created):
            if key.removeprefix("staging/") in self.journal_keys:
                continue
            try:
                if storage.delete_object(key) is not True:
                    logger.error("clone_asset_cleanup_failed", extra={"object_key": key})
            except Exception:
                logger.exception("clone_asset_cleanup_failed", extra={"object_key": key})


@contextmanager
def clone_transaction():
    """Own the outer commit so DB/quota rollback always cleans enlisted fresh objects.

    A nested savepoint cannot observe a later caller rollback. Durable atomic therefore
    rejects nesting instead of pretending to provide rollback cleanup in that case.
    """
    copies = AssetCopies()
    try:
        with transaction.atomic(durable=True):
            # on_commit callbacks run from atomic.__exit__, after the DB commit.
            # Mark it first so a later non-robust callback cannot erase live assets.
            transaction.on_commit(lambda: setattr(copies, "committed", True), robust=True)
            yield copies
    except BaseException:
        if not copies.committed:
            copies.cleanup()
        raise
