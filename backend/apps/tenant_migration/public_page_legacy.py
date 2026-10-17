"""Narrow older-archive admission and explicitly accounted reconstruction.

Only the frozen page additions are optional. Unknown columns and missing unrelated
datasets retain archive_stream's fail-closed behavior. Modern pointer IDs are never
reconstructed from timestamps or substituted with a newer revision.
"""

import csv
from django.apps import apps
from django.db import connection
from .catalog_public_pages import EXPORTED_FIELDS
from .insertion_errors import ImportVerificationError

LEGACY_ADDITIONS = {
    "makerspaces.PublicHandle": {"makerspace_id": None, "organization_id": None},
    "events.EventPage": {"draft_revision_id": None, "published_revision_id": None, "editorial_document": {}},
    "events.EventSession": {"identity_id": None},
}


def legacy_archive(archive):
    path = archive.root / "events/pages.csv"
    if not path.exists():
        return False
    with path.open(encoding="utf-8", newline="") as handle:
        columns = next(csv.reader(handle), [])
    return "draft_revision_id" not in columns and "published_revision_id" not in columns


def missing_dataset_allowed(archive, label):
    return label in EXPORTED_FIELDS and legacy_archive(archive)


def missing_columns_allowed(archive, label, missing):
    return bool(missing) and missing <= LEGACY_ADDITIONS.get(label, {}).keys() and legacy_archive(archive)


def reconstructed_field(label, field):
    values = LEGACY_ADDITIONS.get(label, {})
    if field.attname in values:
        return True, values[field.attname]
    return False, None


def identity_for_legacy_session(row, archive):
    Identity = apps.get_model("events.EventSessionIdentity")
    Alias = apps.get_model("events.EventSessionAlias")
    identity = Identity.objects.create(page_id=row["page_id"])
    alias = Alias.objects.create(page_id=row["page_id"], identity=identity, slug=row["slug"])
    record(archive, Identity, identity.pk, row["page_id"])
    record(archive, Alias, alias.pk, row["page_id"])
    return identity.pk


def record(archive, model, pk, page_id):
    if not hasattr(archive, "public_page_reconstruction"):
        archive.public_page_reconstruction = {}
    label = model._meta.label
    archive.public_page_reconstruction[label] = archive.public_page_reconstruction.get(label, 0) + 1
    with connection.cursor() as cursor:
        cursor.execute("""CREATE TEMP TABLE IF NOT EXISTS tenant_import_page_reconstruction (
            model_label text NOT NULL, target_pk text NOT NULL, page_id bigint NOT NULL,
            PRIMARY KEY(model_label,target_pk)) ON COMMIT DROP""")
        cursor.execute("INSERT INTO tenant_import_page_reconstruction VALUES (%s,%s,%s)", [label, str(pk), page_id])


def reconstruct_drafts(archive, pk_map):
    if not legacy_archive(archive):
        return
    try:
        Page = apps.get_model("events.EventPage")
    except LookupError:
        return
    from apps.events.website_revisions import save_draft
    for source in archive.rows("events.EventPage"):
        page = Page.objects.get(pk=pk_map.lookup(Page, source["id"]))
        revision = save_draft(page)
        record(archive, type(revision), revision.pk, page.pk)
        for ref in revision.asset_references.all():
            record(archive, type(ref), ref.pk, page.pk)


def verify_reconstruction(archive):
    expected = getattr(archive, "public_page_reconstruction", {})
    if not expected:
        return
    actual = {}
    after = ("", "")
    with connection.cursor() as cursor:
        while True:
            cursor.execute("""SELECT model_label,target_pk,page_id FROM tenant_import_page_reconstruction
                WHERE (model_label,target_pk)>(%s,%s) ORDER BY model_label,target_pk LIMIT 500""", after)
            batch = cursor.fetchall()
            if not batch:
                break
            for label, pk, page_id in batch:
                model = apps.get_model(label)
                path = "revision__page_id" if label.endswith(("RevisionAsset", "RevisionMember")) else "page_id"
                if not model.objects.filter(pk=pk, **{path: page_id}).exists():
                    raise ImportVerificationError("Legacy page reconstruction lost ownership or an expected row.")
                actual[label] = actual.get(label, 0) + 1
            after = (batch[-1][0], batch[-1][1])
    if actual != expected:
        raise ImportVerificationError("Legacy page reconstruction count mismatch.")
