"""Retire replaced originals and abandoned account uploads without touching event copies."""
from datetime import timedelta

from django.utils import timezone

from apps.audit.services import record
from apps.encryption.account_write_fence import account_write

from .access import require_owner
from .crypto import open_value
from .errors import SavedDetailsError
from .models import MemberSavedAsset, MemberSavedDetail, SavedDetailUpdateIntent, SavedDetailsObjectCleanup


def retire_unreferenced_resumes(actor_id):
    current = MemberSavedDetail.objects.filter(user_id=actor_id, field_key="resume").first()
    selected = open_value(current, "value_envelope") if current and not current.deleted_at else None
    with account_write(actor_id):
        actor = require_owner(actor_id, lock=True)
        live = MemberSavedDetail.objects.filter(user=actor, field_key="resume").first()
        if (current.version if current else 0) != (live.version if live else 0):
            return  # retry with the current owner's selection, never guess a reference
        pending_resume = SavedDetailUpdateIntent.objects.filter(user=actor, state="pending", chosen_fields__contains=["resume"]).exists()
        assets = MemberSavedAsset.objects.select_for_update().filter(user=actor).exclude(state__in=["deleting", "deleted"]).order_by("pk")
        now = timezone.now()
        for asset in assets:
            asset.next_cleanup_at = now + timedelta(hours=6)
            is_selected = selected and selected.get("asset_id") == asset.pk
            obsolete = asset.last_selected_at is not None or asset.created_at <= now - timedelta(hours=24)
            if not is_selected and obsolete and not pending_resume:
                asset.state, asset.version = "deleting", asset.version + 1
                SavedDetailsObjectCleanup.objects.create(object_keys=list(set([asset.object_key, asset.staging_key, asset.verification_key, *asset.cleanup_keys])), next_attempt_at=now)
                record(actor, "account.saved_resume_retired", target=asset)
            asset.save(update_fields=["state", "version", "next_cleanup_at"])
