"""The ONLY portable FK edges omitted from insertion dependency ordering.

All rows still receive their single immutable INSERT. Only these mutable page
draft pointers may be assigned after dependent reference rows have been inserted.
"""

from django.apps import apps
from django.db import connection
from .insertion_errors import ImportVerificationError
from apps.backup.capture_managers import every_row

PAGE_POINTERS = {
    ("makerspaces.MakerspacePublicPage", "draft_revision"): "makerspaces.MakerspacePublicPageRevision",
    ("makerspaces.MakerspacePublicPage", "published_revision"): "makerspaces.MakerspacePublicPageRevision",
    ("events.EventPage", "draft_revision"): "events.EventPageRevision",
    ("events.EventPage", "published_revision"): "events.EventPageRevision",
}


def deferred_pointer(field):
    target = PAGE_POINTERS.get((field.model._meta.label, field.name))
    if target is None:
        return False
    if not field.concrete or not field.null or field.related_model._meta.label != target:
        raise ImportVerificationError("Reviewed page-pointer schema changed.")
    return True


def apply_page_pointer_fixups(archive, pk_map):
    from .public_page_legacy import reconstruct_drafts, legacy_archive, verify_reconstruction
    reconstruct_drafts(archive, pk_map)
    report = {}
    for (label, field), target_label in PAGE_POINTERS.items():
        if field != "draft_revision":
            continue
        try:
            model, revision_model = apps.get_model(label), apps.get_model(target_label)
        except LookupError:
            continue
        for source in archive.rows(label):
            target_pk = pk_map.lookup(model, source["id"])
            value = source.get("draft_revision_id")
            if value:
                draft = pk_map.lookup(revision_model, value)
                if not every_row(revision_model).filter(pk=draft, page_id=target_pk).exists():
                    raise ImportVerificationError(f"Wrong-owner or missing draft for {label}.")
            else:
                existing = every_row(model).get(pk=target_pk)
                draft = existing.draft_revision_id if legacy_archive(archive) and label == "events.EventPage" else None
                if draft is None and every_row(revision_model).filter(page_id=target_pk).exists():
                    raise ImportVerificationError(f"Saved {label} has no exact archived draft pointer.")
                if draft is None and label == "events.EventPage" and (existing.sections.exists() or existing.sessions.exists()):
                    raise ImportVerificationError("A nonempty modern website has no archived draft pointer.")
            changes = {"draft_revision_id": draft, "published_revision_id": None}
            if label == "events.EventPage":
                changes["released"] = False
            if every_row(model).filter(pk=target_pk).update(**changes) != 1:
                raise ImportVerificationError("Page shell is missing during pointer fixup.")
            actual = every_row(model).get(pk=target_pk)
            if actual.draft_revision_id != draft or actual.published_revision_id is not None:
                raise ImportVerificationError("Page pointer fixup did not persist exactly.")
            if label == "events.EventPage":
                from .public_page_verification import verify_event_draft
                verify_event_draft(actual)
            counts = report.setdefault(label, {"restored": 0, "empty_shells": 0})
            counts["restored" if draft else "empty_shells"] += 1
    with connection.cursor() as cursor:
        cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
        cursor.execute("SET CONSTRAINTS ALL DEFERRED")
    verify_reconstruction(archive)
    return report
