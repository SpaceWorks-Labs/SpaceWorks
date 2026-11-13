"""Full materialization, including old headers and exact selected draft fixups."""
import csv
from datetime import timedelta
from pathlib import Path
import pytest
from apps.events.models import Event
from apps.events.models_website import EventPage, EventPageSection, EventSessionSpeaker
from apps.makerspaces.models_public_pages import MakerspacePublicPage, MakerspacePublicPageRevision
from apps.makerspaces.public_page_contract import empty_document
from apps.tenant_migration.archive_stream import PORTABLE_DATASETS
from apps.tenant_migration.catalog_public_pages import EXPORTED_FIELDS
from apps.tenant_migration.materialization import materialize_tenant
from apps.tenant_migration.insertion_errors import ImportVerificationError
from tests.data_export.portable_helpers import make_space, make_user
from tests.encryption.conftest import enabled_encryption
from tests.tenant_migration.materialization_helpers import portable_import_case
from tests.tenant_migration.object_helpers import memory_objects  # noqa: F401
from tests.events.website_helpers import make_page, make_session, snapshot

pytestmark = pytest.mark.django_db(transaction=True)


def source_pages(space, user, request, *, builder=True):
    event = Event.objects.get(makerspace=space, title="Portable workshop")
    page = make_page(makerspace=space, event=event, released=True)
    speaker = EventPageSection.objects.create(page=page, kind="speaker", slug="ada", title="Published Ada", visibility="published")
    talk = make_session(page=page, slug="talk", title="Talk", starts_at=event.starts_at,
                        ends_at=event.ends_at, visibility="published")
    EventSessionSpeaker.objects.create(session=talk, speaker=speaker)
    snapshot(page)
    speaker.title = "Saved draft Ada"
    speaker.save(update_fields=["title"])
    from apps.events.website_revisions import save_draft
    save_draft(page, user)
    if builder:
        own = MakerspacePublicPage.objects.create(makerspace=space)
        first = MakerspacePublicPageRevision.objects.create(page=own, document=empty_document("makerspace"), created_by=user)
        own.draft_revision = own.published_revision = first
        own.save(update_fields=["draft_revision", "published_revision"])
    return page.pk


def rewrite(root, label, transform):
    path = Path(root) / PORTABLE_DATASETS[label].path
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fields, rows = reader.fieldnames, list(reader)
    fields, rows = transform(fields, rows)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def strip_new_graph(root):
    additions = {"makerspaces.PublicHandle": {"makerspace_id", "organization_id"},
        "events.EventPage": {"draft_revision_id", "published_revision_id", "editorial_document"},
        "events.EventSession": {"identity_id"}, "events.EventPageSection": {"is_working"}}
    for label, dropped in additions.items():
        rewrite(root, label, lambda fields, rows, dropped=dropped: (
            [key for key in fields if key not in dropped],
            [{key: value for key, value in row.items() if key not in dropped} for row in rows]))
    for label in EXPORTED_FIELDS:
        (Path(root) / PORTABLE_DATASETS[label].path).unlink()


@pytest.mark.parametrize("legacy", [False, True])
def test_full_archive_materializes_snapshots_identities_and_publication_reset(memory_objects, legacy):
    with enabled_encryption():
        source = make_space("pages-legacy" if legacy else "pages-modern")
        user = make_user("page-archive")
        with portable_import_case(source, user,
                prepare_source=lambda *args: source_pages(*args, builder=not legacy)) as case:
            case.decide_walk_in(user)
            if legacy:
                strip_new_graph(case.root)
            result = materialize_tenant(case.root, case.job, case.carried,
                target_identity={"slug": "page-roundtrip-target"})
    page = EventPage.objects.get(makerspace_id=result.target_makerspace_id)
    assert page.draft_revision_id and not page.released and page.published_revision_id is None
    session = page.sessions.get()
    assert session.identity.page_id == page.pk
    assert page.session_aliases.get().identity_id == session.identity_id
    assert session.speaker_links.get().speaker.page_id == page.pk
    assert page.draft_revision.document["sections"][0]["title"] == "Saved draft Ada"
    assert page.draft_revision.document["sessions"][0]["session_id"] == str(session.identity_id)
    if not legacy:
        builder = MakerspacePublicPage.objects.get(makerspace_id=result.target_makerspace_id)
        assert builder.draft_revision_id and builder.published_revision_id is None


@pytest.mark.parametrize("corruption", ["missing", "wrong_owner"])
def test_materialization_refuses_missing_or_wrong_owner_exact_draft(memory_objects, corruption):
    with enabled_encryption():
        source = make_space("page-bad-fixup")
        user = make_user("page-bad-fixup")
        def prepare(space, user, request):
            source_pages(space, user, request)
            event = Event.objects.create(makerspace=space, title="Other page", starts_at=request.created_at,
                ends_at=request.created_at + timedelta(hours=1))
            return make_page(makerspace=space, event=event).draft_revision_id
        with portable_import_case(source, user, prepare_source=prepare) as case:
            case.decide_walk_in(user)
            if corruption == "missing":
                rewrite(case.root, "events.EventPage", lambda fields, rows: (fields, [
                    {**row, "draft_revision_id": ""} if index == 0 else row for index, row in enumerate(rows)]))
            else:
                rewrite(case.root, "events.EventPage", lambda fields, rows: (fields, [
                    {**row, "draft_revision_id": str(case.source_data)} if index == 0 else row
                    for index, row in enumerate(rows)]))
            with pytest.raises(ImportVerificationError):
                materialize_tenant(case.root, case.job, case.carried,
                    target_identity={"slug": "refused-page-target"})
