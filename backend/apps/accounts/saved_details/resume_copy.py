"""Typed account→event copy input. Consumer creates independently owned bytes.

No event model, route or caller-supplied destination enters this account module.
The event asset owner must separately establish participant eligibility/quota.
"""
from django.utils.translation import gettext
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Iterator

from django.utils import timezone

from apps.encryption.account_readiness import assert_ready
from apps.makerspaces.private_upload_transport import ObjectLocator, resolve_range, stream_private

from . import storage
from .access import owner_read_gate
from .assets import owned_asset
from .errors import SavedDetailsError
from .crypto import open_value
from .models import MemberSavedDetail


@dataclass(frozen=True)
class SavedResumeCopy:
    sha256: str
    size_bytes: int
    canonical_mime: str
    chunks: Iterator[bytes] = field(repr=False)


def prepare_saved_resume_copy(*, actor_id, asset_id, sha256):
    assert_ready()
    authorize_owner = owner_read_gate(actor_id)
    source = owned_asset(actor_id, asset_id)

    def authorize():
        authorize_owner()
        current = owned_asset(actor_id, asset_id)
        from .asset_policy import require_ready
        require_ready(current)
        if current.state != "ready" or current.sha256 != sha256 or current.version != source.version:
            raise SavedDetailsError("asset_not_ready", gettext("Choose your own ready résumé."), 409)
    authorize()
    chunks = stream_private(
        locator=ObjectLocator(bucket=storage.bucket(), key=source.object_key, version_id=source.final_version_id or None),
        byte_range=resolve_range(None, source.size_bytes), reader=storage.read_range,
        authorize=authorize, clock=timezone.now, not_after=timezone.now() + timedelta(minutes=2),
    )
    return SavedResumeCopy(source.sha256, source.size_bytes, source.canonical_mime, chunks)


def prepare_saved_resume_selection(*, actor_id, saved_asset_id, saved_detail_version):
    """B's §12C from-saved input resolves the current private selection server-side."""
    authorize_owner = owner_read_gate(actor_id)
    detail = MemberSavedDetail.objects.filter(user_id=actor_id, field_key="resume", deleted_at__isnull=True).first()
    if detail is None or detail.version != saved_detail_version:
        raise SavedDetailsError("saved_detail_changed", gettext("Review your saved résumé selection."), 409)
    value = open_value(detail, "value_envelope")
    if not isinstance(value, dict) or value.get("asset_id") != saved_asset_id:
        raise SavedDetailsError("saved_detail_changed", gettext("Review your saved résumé selection."), 409)
    copied = prepare_saved_resume_copy(actor_id=actor_id, asset_id=saved_asset_id, sha256=value["sha256"])

    def check_selection():
        authorize_owner()
        if not MemberSavedDetail.objects.filter(pk=detail.pk, user_id=actor_id,
                version=saved_detail_version, deleted_at__isnull=True).exists():
            raise SavedDetailsError("saved_detail_changed", gettext("Your saved résumé selection changed."), 409)

    def chunks():
        stream = iter(copied.chunks)
        while True:
            check_selection()
            try:
                chunk = next(stream)
            except StopIteration:
                return
            check_selection()
            yield chunk
    return SavedResumeCopy(copied.sha256, copied.size_bytes, copied.canonical_mime, chunks())
