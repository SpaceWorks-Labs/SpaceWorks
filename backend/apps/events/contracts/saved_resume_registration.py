"""P -> B independently owned resume copy; source keys never leave Accounts."""

from dataclasses import dataclass, field
from hashlib import sha256

from apps.accounts.saved_details.resume_copy import prepare_saved_resume_selection
from apps.events.submissions.errors import SubmissionError
from apps.events.submissions.models_assets import HackathonParticipantAsset
from apps.transaction_guards import in_domain_transaction


@dataclass(frozen=True)
class PreparedResume:
    actor_id: int
    saved_asset_id: int
    saved_detail_version: int
    size_bytes: int
    sha256: str
    source: object = field(repr=False)
    filename: str = "resume.pdf"


class SavedResumeProvider:
    def __init__(self, storage):
        self.storage = storage

    def prepare(self, *, actor_id, saved_asset_id, saved_detail_version):
        if in_domain_transaction():
            raise RuntimeError("Prepare a saved resume before event transactions.")
        source = prepare_saved_resume_selection(actor_id=actor_id, saved_asset_id=saved_asset_id,
                                                saved_detail_version=saved_detail_version)
        return PreparedResume(actor_id, saved_asset_id, saved_detail_version, source.size_bytes, source.sha256, source)

    def copy_to_event(self, *, prepared, event_id, asset_id, target_key):
        if in_domain_transaction():
            raise RuntimeError("Copy saved bytes outside event transactions.")
        if not isinstance(prepared, PreparedResume):
            raise TypeError("Use an owner-prepared resume.")
        def target_live():
            if not HackathonParticipantAsset.objects.filter(pk=asset_id, event_id=event_id,
                member_id=prepared.actor_id, state="copying", verification_key=target_key,
                declared_bytes=prepared.size_bytes, work__saved_asset_id=prepared.saved_asset_id,
                work__saved_detail_version=prepared.saved_detail_version).exists():
                raise SubmissionError("not_found", 404)
        target_live()
        content = bytearray()
        try:
            for chunk in prepared.source.chunks:
                content.extend(chunk)
                if len(content) > min(prepared.size_bytes, 10*1024*1024):
                    raise SubmissionError("upload_size_mismatch", 413)
        finally:
            close = getattr(prepared.source.chunks, "close", None)
            if close:
                close()
        if len(content) != prepared.size_bytes or sha256(content).hexdigest() != prepared.sha256:
            raise SubmissionError("saved_detail_changed", 409)
        target_live()
        from apps.events.submissions.storage_promotion import promote
        result = promote(self.storage, source=None, target_key=target_key, sha256=prepared.sha256,
                         canonical_bytes=bytes(content), mime="application/pdf")
        # A revoked selection during the object write cannot publish ready bytes.
        prepare_saved_resume_selection(actor_id=prepared.actor_id, saved_asset_id=prepared.saved_asset_id,
                                       saved_detail_version=prepared.saved_detail_version)
        target_live()
        return result
