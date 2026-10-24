"""Called only inside the existing authorized Events/tenant purge transaction."""
from django.apps import apps
from django.db import connection
from django.db.models import Q

from .purge_events_programme_catalog import CLEAR_POINTERS, PURGE_ORDER


def delete_programme_rows(makerspace):
    if not connection.in_atomic_block:
        raise RuntimeError("Programme purge requires the enclosing authorized purge transaction.")
    total, labels = 0, set()
    # Exact private byte locators must outlive the graph which owns the print job.
    from apps.events.certificates.print_cleanup import capture_purge_locked
    event_ids = apps.get_model("events.Event").objects.filter(makerspace=makerspace).values_list("pk", flat=True)
    capture_purge_locked(event_ids)
    # Certificates protect both role and award subjects, so remove them first.
    count, deleted = apps.get_model("events.EventAttendanceCertificate")._base_manager.filter(
        event__makerspace=makerspace,
    ).delete()
    total += count
    labels.update(deleted)
    apps.get_model("events.EventBroadcast")._base_manager.filter(makerspace=makerspace).update(
        status="cancelled", confirmed_preview=None, available_at=None,
    )
    for label, field in CLEAR_POINTERS:
        apps.get_model(label)._base_manager.filter(event__makerspace=makerspace).update(**{field: None})
    for label, owner in PURGE_ORDER:
        model = apps.get_model(label)
        rows = model._base_manager.filter(**{owner: makerspace})
        if label == "events.SubmissionAssetWork":
            rows = model._base_manager.filter(Q(asset__event__makerspace=makerspace)
                | Q(participant_asset__event__makerspace=makerspace))
        if label in {"events.EventResultRevision", "events.SubmissionSnapshot"}:
            # Self-PROTECT correction/amendment chains are removed newest first.
            for pk in rows.order_by("-pk").values_list("pk", flat=True).iterator(chunk_size=500):
                count, deleted = model._base_manager.filter(pk=pk).delete()
                total += count
                labels.update(deleted)
        else:
            count, deleted = rows.delete()
            total += count
            labels.update(deleted)
    return total, frozenset(labels)
