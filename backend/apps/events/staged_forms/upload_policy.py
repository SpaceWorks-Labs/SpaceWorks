"""An R stage reference can resolve only its owner's pinned stage file."""
from django.utils import timezone
from .upload_models import StageFormAsset


def resolve_reference(*, assignment, question, reference, locked=False):
    if question.get("file", {}).get("purpose") != "stage_form_file":
        return False
    rows = StageFormAsset.objects
    if locked:
        rows = rows.select_for_update()
    row = rows.filter(pk=reference["asset_id"], assignment=assignment, event_id=assignment.event_id,
        owner_member_id=assignment.owner_member_id, form_revision_id=assignment.pinned_form_revision_id,
        purpose="stage_form_file", question_id=question["id"], generation=reference["generation"],
        sha256=reference["sha256"], state__in=("ready", "attached")).first()
    return bool(row and row.scan_status in ("clean", "skipped") and row.canonical_mime
        and row.actual_bytes is not None and row.actual_bytes <= question["file"]["max_bytes_each"]
        and (row.expires_at is None or timezone.now() < row.expires_at))
