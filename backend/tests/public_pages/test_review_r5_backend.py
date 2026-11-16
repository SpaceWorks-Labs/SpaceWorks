"""Review round 5 (backend core + 5b): one regression per finding."""

import logging
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied
from rest_framework.test import APIClient

from apps.makerspaces import public_page_assets as assets, public_page_services as pages
from apps.makerspaces.models import Makerspace
from apps.makerspaces.models_page_cleanup import PublicPageObjectCleanup as Cleanup
from tests.events.collab_helpers import client_for, make_staff
from tests.public_pages.test_l1_assets import picture, private_store  # noqa: F401  (fixture)
from tests.public_pages.test_review_r5_contracts import published_cover

pytestmark = pytest.mark.django_db(transaction=True)


def governed_org(slug="r5-builders"):
    from apps.accounts.models import User
    from apps.organizations.models import Organization, OrganizationMembership
    org = Organization.objects.create(name="R5 builders", slug=slug, public_profile_enabled=True)
    governor = User.objects.create_user(username=f"{slug}-governor", account_kind="member")
    OrganizationMembership.objects.create(organization=org, user=governor,
                                          governance_actions=["manage_organization_profile"])
    return org, governor


@pytest.fixture
def hosts(settings):
    settings.INFRA_HOSTS = ["testserver", "localhost", "127.0.0.1"]
    settings.ALLOWED_HOSTS = ["*"]
    settings.PUBLIC_APP_BASE_URL = "http://testserver"


# [P2] Organization page reads: Origin/Referer fail closed; an IP infra host is not a tenant.
def test_organization_page_scope_checks_origin_and_ip_hosts(hosts, private_store):
    Makerspace.objects.create(name="Domainless", slug="domainless")  # frontend_domain is NULL
    Makerspace.objects.create(name="Tenant", slug="tenant-r5", frontend_domain="lab.r5.test",
                              frontend_domain_status=Makerspace.DomainStatus.VERIFIED)
    org, governor = governed_org()
    published_cover("organization", org, governor, "r5.org")
    url = f"/api/v1/public/organizations/{org.slug}/page/"
    client = APIClient()
    assert client.get(url).status_code == 200
    assert client.get(url, HTTP_HOST="127.0.0.1").status_code == 200
    assert client.get(url, HTTP_ORIGIN="https://unknown.example").status_code == 404
    assert client.get(url, HTTP_REFERER="https://unknown.example/page").status_code == 404
    assert client.get(url, HTTP_HOST="lab.r5.test").status_code == 404
    # A tenant browser Origin may still read the global organization page.
    assert client.get(url, HTTP_ORIGIN="https://lab.r5.test").status_code == 200


# [P2] Superadmins keep the existing organization profile API, including takedown.
def test_superadmin_can_take_down_an_organization_profile(hosts, private_store):
    from apps.accounts.models import User
    from apps.organizations.models_public_pages import OrganizationPublicPage
    from apps.organizations.services_profiles import update_profile
    org, governor = governed_org()
    published_cover("organization", org, governor, "r5.org")
    root = User.objects.create_superuser(username="r5-root", password=None)
    updated = update_profile(org, actor=root, public_profile_enabled=False, description="Taken down")
    assert updated.public_profile_enabled is False and updated.description == "Taken down"
    assert OrganizationPublicPage.objects.get(organization=org).published_revision_id is None
    # Re-enabling a builder revision is page publication, which stays owner-only.
    with pytest.raises(Exception):
        update_profile(org, actor=root, public_profile_enabled=True)


# [P2] Inventory stats count only what the public catalogue lists.
def test_inventory_stats_skip_archived_and_hidden_catalogue(hosts, monkeypatch):
    from apps.inventory.models import InventoryProduct
    from apps.makerspaces import editions
    from apps.makerspaces.public_page_derived import derived_payload
    space = Makerspace.objects.create(name="Stats", slug="stats-r5", public_site_enabled=True,
                                      public_inventory_enabled=True)
    space.enabled_modules = sorted({*(space.enabled_modules or []), "public_inventory"})
    space.enabled_features = sorted({*(space.enabled_features or []), "loans.enabled"})
    space.save(update_fields=["enabled_modules", "enabled_features"])
    common = dict(makerspace=space, is_public=True, show_public_count=True, public_availability_mode="exact_count")
    InventoryProduct.objects.create(name="Live", total_quantity=5, available_quantity=5, **common)
    InventoryProduct.objects.create(name="Retired", total_quantity=7, available_quantity=7, is_archived=True, **common)
    payload = {"title": "", "show_published_event_count": False, "show_public_inventory_units": True,
               "publish_public_member_count": False}
    result = derived_payload("makerspace", space, "stats", payload)
    assert result["metrics"]["public_exact_count_subset_units"] == 5
    monkeypatch.setattr(editions, "hidden_module_keys", lambda: frozenset({"public_inventory"}))
    assert derived_payload("makerspace", space, "stats", payload) is None


@pytest.fixture
def deleted(monkeypatch):
    from apps.makerspaces import website_assets
    keys = []
    monkeypatch.setattr(website_assets, "delete_object", lambda key: keys.append(key) or True)
    return keys


# [P2] Completed event receipts stop repairing and cannot starve pending deletions.
def test_old_event_receipts_stop_and_pending_cleanup_goes_first(hosts, deleted):
    from apps.makerspaces.public_page_asset_cleanup import clean_object, sweep
    space = Makerspace.objects.create(name="Sweep", slug="sweep-r5")
    now = timezone.now()
    old = Cleanup.objects.create(owner_kind="event", owner_id=space.pk, page_id=1, size_bytes=4,
        object_key=f"events/website/{space.pk}/1/old.webp", storage_accounted=False, ownership_proven=True,
        completed_at=now - timedelta(hours=25), due_at=now - timedelta(hours=1))
    recent = Cleanup.objects.create(owner_kind="event", owner_id=space.pk, page_id=1, size_bytes=4,
        object_key=f"events/website/{space.pk}/1/recent.webp", storage_accounted=False, ownership_proven=True,
        completed_at=now - timedelta(hours=1), due_at=now - timedelta(hours=2))
    pending = Cleanup.objects.create(owner_kind="makerspace", owner_id=space.pk, page_id=9, size_bytes=4,
        object_key=f"pages/makerspaces/{space.pk}/9/pending.webp", storage_accounted=False,
        due_at=now - timedelta(minutes=1))
    assert old.pk < recent.pk < pending.pk
    assert sweep(limit=1)["deleted"] == 1
    pending.refresh_from_db()
    assert pending.completed_at and pending.object_key in deleted
    assert not clean_object(old.pk)
    assert not any(key.endswith("old.webp") for key in deleted)  # Out of window: never re-deleted.
    sweep(limit=10)
    assert not any(key.endswith("old.webp") for key in deleted)
    assert any(key.endswith("recent.webp") for key in deleted)  # Inside the window it still repairs.


# [P3] Uploads refuse unauthorized actors before reading or decoding bytes.
def test_upload_checks_authority_before_reading_the_file(page_owner):
    space, _ = page_owner
    outsider = make_staff(Makerspace.objects.create(name="Other", slug="other-r5"), "outsider")

    class Untouchable:
        def read(self, *args):
            pytest.fail("the upload body was read before authority was checked")

    with pytest.raises(Exception) as refused:
        assets.upload("makerspace", space.pk, actor=outsider, version=0, file=Untouchable(), alt_text="x")
    assert refused.type.__name__ in {"NotFound", "PermissionDenied", "Http404"}
    from django.contrib.auth.models import AnonymousUser
    with pytest.raises(PermissionDenied):
        assets.upload("makerspace", space.pk, actor=AnonymousUser(), version=0, file=Untouchable(), alt_text="x")


# [P3] Editor GETs take no tenant write fence and no row locks.
def test_editor_reads_skip_write_fence_and_row_locks(page_owner, private_store, monkeypatch):
    from io import BytesIO
    from apps.evidence import storage
    from apps.tenant_migration import gate_runtime
    space, actor = page_owner
    _, asset_id = published_cover("makerspace", space, actor, "reads.lab")
    monkeypatch.setattr(storage, "object_size", lambda key: 4)
    monkeypatch.setattr(storage, "_client", lambda: SimpleNamespace(get_object=lambda **kw: {"Body": BytesIO(b"webp")}))

    def fenced(*args, **kwargs):
        raise AssertionError("a read took the tenant write fence")
    monkeypatch.setattr(gate_runtime, "assert_write_allowed", fenced)
    client = client_for(actor)
    for name, kwargs, query in (("editor", {}, ""), ("revisions", {}, ""), ("handle-availability", {}, "?handle=free.lab"),
                                ("asset", {"asset_id": asset_id}, "")):
        url = reverse(f"makerspace-public-page-{name}", kwargs={"pk": space.pk, **kwargs}) + query
        with CaptureQueriesContext(connection) as queries:
            response = client.get(url)
        assert response.status_code == 200, (name, response.status_code)
        assert not any("FOR UPDATE" in row["sql"] for row in queries.captured_queries), name
    outsider = make_staff(Makerspace.objects.create(name="Elsewhere", slug="elsewhere-r5"), "reader")
    assert client_for(outsider).get(reverse("makerspace-public-page-editor", kwargs={"pk": space.pk})).status_code in {403, 404}


# [P3] A makerspace page description comes from its first enabled About section.
def test_makerspace_page_description_uses_the_about_section(page_owner, private_store):
    from apps.makerspaces.public_page_access import public_page
    from apps.makerspaces.public_page_projection import projection
    space, actor = page_owner
    state = pages.change_handle("makerspace", space.pk, actor=actor, version=0, handle="about.lab")
    document = state["document"]
    document["sections"].insert(0, {"id": str(uuid4()), "type": "about", "enabled": False,
                                    "payload": {"title": "Hidden", "markdown": "Not this one"}})
    document["sections"].insert(1, {"id": str(uuid4()), "type": "about", "enabled": True, "payload": {
        "title": "About", "markdown": "## Welcome\nA *community* workshop. See [our tools](https://example.test/tools)."}})
    state = pages.save("makerspace", space.pk, actor=actor, version=state["version"], document=document)
    pages.publish("makerspace", space.pk, actor=actor, version=state["version"],
                  draft_revision_id=state["draft_revision_id"])
    space.refresh_from_db()
    payload = projection("makerspace", space, public_page("makerspace", space))
    assert payload["description"] == "Welcome A community workshop. See our tools."


# [P3] Sitemap pages are one query per owner kind; tenant hosts skip organizations.
def test_sitemap_page_urls_are_bulk_and_tenant_hosts_skip_organizations(hosts, private_store, rf):
    from apps.makerspaces.public_page_share import sitemap_page_urls
    from apps.makerspaces.servability import servable_queryset
    owners = []
    for index in range(3):
        space = Makerspace.objects.create(name=f"Map {index}", slug=f"map-{index}", public_site_enabled=True)
        published_cover("makerspace", space, make_staff(space), f"map{index}.lab")
        owners.append(space)
    org, governor = governed_org()
    published_cover("organization", org, governor, "map.org")
    spaces = servable_queryset(Makerspace.objects.all())
    request = rf.get("/sitemap.xml", HTTP_HOST="testserver")
    with CaptureQueriesContext(connection) as queries:
        urls = list(sitemap_page_urls(request, spaces=spaces))
    assert {url.rsplit("/", 1)[1] for url in urls} == {"map0.lab", "map1.lab", "map2.lab", "map.org"}
    handle_queries = [row for row in queries.captured_queries if "makerspaces_publichandle" in row["sql"]]
    assert len(handle_queries) == 2
    tenant = owners[0]
    Makerspace.objects.filter(pk=tenant.pk).update(frontend_domain="map0.r5.test",
                                                   frontend_domain_status=Makerspace.DomainStatus.VERIFIED)
    request = rf.get("/sitemap.xml", HTTP_HOST="map0.r5.test")
    urls = list(sitemap_page_urls(request, spaces=spaces))
    assert urls == ["https://map0.r5.test/map0.lab"]


def test_team_handles_are_one_query_and_event_cards_join_makerspace(event_owner):
    from apps.accounts.models import User
    from apps.makerspaces.models import MakerspaceMembership
    from apps.makerspaces.models_profiles import MemberProfile, PublicHandle
    from apps.makerspaces.public_page_derived import event_cards
    from apps.makerspaces.public_page_projection import project_team
    space, _, _ = event_owner
    space.enabled_modules = sorted({*(space.enabled_modules or []), "membership"})
    space.save(update_fields=["enabled_modules"])
    references, entries = [], []
    for index in range(3):
        user = User.objects.create_user(username=f"team-r5-{index}", email=f"team-r5-{index}@example.test")
        membership = MakerspaceMembership.objects.create(makerspace=space, user=user, role="custom",
                                                         assigned_role=space.roles.get(slug="member"))
        profile = MemberProfile.objects.create(membership=membership, public_visible=True,
                                               public_consented_at=timezone.now())
        PublicHandle.objects.create(user=user, profile=profile, handle=f"team.r5{index}", changed_at=timezone.now())
        from apps.makerspaces.models import AccountProfile
        AccountProfile.objects.update_or_create(user=user, defaults={"public_visible": True, "public_consented_at": timezone.now()})
        slot = str(uuid4())
        references.append(SimpleNamespace(slot=slot, profile=profile))
        entries.append({"id": slot, "kind": "member", "role": "Mentor", "member_slot_id": slot})
    revision = SimpleNamespace(member_references=SimpleNamespace(select_related=lambda *args: references))
    with CaptureQueriesContext(connection) as queries:
        team = project_team(entries, revision, None)
    assert [row["handle"] for row in team] == ["team.r50", "team.r51", "team.r52"]
    assert len([row for row in queries.captured_queries if "makerspaces_publichandle" in row["sql"]]) == 1
    with CaptureQueriesContext(connection) as queries:
        cards, count = event_cards("makerspace", space)
    if count:
        assert len([row for row in queries.captured_queries if 'FROM "makerspaces_makerspace"' in row["sql"]]) == 0


# [P3] OpenAPI documents 400 for the paginated organization collections.
def test_organization_collections_document_400():
    from drf_spectacular.generators import SchemaGenerator
    schema = SchemaGenerator().get_schema(request=None, public=True)
    paths = {path: spec for path, spec in schema["paths"].items() if path.startswith("/api/v1/public/organizations/")}
    collections = [path for path in paths if path.endswith(("/makerspaces/", "/events/"))]
    assert any(path.endswith("/makerspaces/") for path in collections)
    for path in collections:
        assert "400" in paths[path]["get"]["responses"], path


# [P2] Restore verification warns (never refuses) when the counter is below page bytes.
def test_restore_verification_warns_on_low_storage_counter(page_owner, monkeypatch, settings, caplog):
    from apps.backup.public_page_verification import verify_public_pages
    from apps.makerspaces import limits
    from apps.makerspaces.models_public_pages import MakerspacePublicPage, MakerspacePublicPageAsset
    space, _ = page_owner
    monkeypatch.setattr(limits, "resource_limit", lambda owner, key: 1000)
    page = MakerspacePublicPage.objects.create(makerspace=space)
    MakerspacePublicPageAsset.objects.create(page=page, size_bytes=10, alt_text="Uncounted",
                                             object_key=f"pages/makerspaces/{space.pk}/{page.pk}/r5.webp")
    Makerspace.objects.filter(pk=space.pk).update(storage_bytes_used=0)
    with caplog.at_level(logging.WARNING, logger="apps.backup.public_page_verification"):
        assert verify_public_pages()["assets"] == 1
    assert "public_page.restore_storage_counter_below_page_bytes" in caplog.text


# [P2] Cleanup for an absent tenant waits for a slice merge unless a purge is audited.
def test_absent_tenant_cleanup_requires_a_purge_record(hosts, deleted):
    from apps.audit import services as audit
    from apps.makerspaces.public_page_asset_cleanup import clean_object
    absent = (Makerspace.objects.order_by("-pk").values_list("pk", flat=True).first() or 0) + 1000
    jobs = [Cleanup.objects.create(owner_kind=kind, owner_id=absent, page_id=3, size_bytes=4, object_key=key,
                                   ownership_proven=kind == "event", due_at=timezone.now() - timedelta(minutes=1))
            for kind, key in (("makerspace", f"pages/makerspaces/{absent}/3/a.webp"),
                              ("event", f"events/website/{absent}/3/b.webp"))]
    for job in jobs:
        assert not clean_object(job.pk)
    assert deleted == []
    audit.record(None, "makerspace.purge_started", makerspace=None, target=None, meta={"makerspace_id": absent})
    for job in jobs:
        assert clean_object(job.pk)
    assert {key for key in deleted if not key.startswith("staging/")} == {job.object_key for job in jobs}


# [P3] Tenant import key allocation honours page assets and cleanup journals.
def test_import_key_allocation_skips_page_assets_and_cleanup_keys(page_owner, monkeypatch):
    from apps.makerspaces.models_public_pages import MakerspacePublicPage, MakerspacePublicPageAsset
    from apps.tenant_migration import object_storage
    space, _ = page_owner
    monkeypatch.setattr(object_storage, "object_exists", lambda bucket, key: False)
    page = MakerspacePublicPage.objects.create(makerspace=space)
    asset_key = f"pages/makerspaces/{space.pk}/{page.pk}/live.webp"
    MakerspacePublicPageAsset.objects.create(page=page, size_bytes=4, alt_text="Live", object_key=asset_key)
    journal_key = f"pages/makerspaces/{space.pk}/{page.pk}/pending.webp"
    Cleanup.objects.create(owner_kind="makerspace", owner_id=space.pk, page_id=page.pk, size_bytes=4,
                           object_key=journal_key)
    cover_key = f"event/{space.pk}/cover.webp"
    Cleanup.objects.create(owner_kind="event", owner_id=space.pk, page_id=1, size_bytes=4, object_key=cover_key)
    for bucket, key in (("private", asset_key), ("private", journal_key), ("public", cover_key)):
        chosen, remapped = object_storage.choose_target_key(bucket, key, 77)
        assert remapped and chosen != key and chosen.startswith("migrated-objects/77/"), key
    assert object_storage.choose_target_key("private", "pages/makerspaces/1/1/free.webp", 77) == (
        "pages/makerspaces/1/1/free.webp", False)


# [P3] A pre-branch archive is recognised even when Events was tombstoned at the source.
def test_legacy_archive_detected_without_events_dataset(tmp_path):
    from apps.tenant_migration.archive_stream import PORTABLE_DATASETS
    from apps.tenant_migration.public_page_legacy import legacy_archive
    handles = Path(tmp_path) / PORTABLE_DATASETS["makerspaces.PublicHandle"].path
    pages_csv = Path(tmp_path) / PORTABLE_DATASETS["makerspaces.MakerspacePublicPage"].path
    archive = SimpleNamespace(root=Path(tmp_path))
    assert not legacy_archive(archive)  # No evidence either way: fail closed.
    handles.parent.mkdir(parents=True, exist_ok=True)
    handles.write_text("id,user_id,profile_id,handle,claimed_at,changed_at\n", encoding="utf-8")
    assert legacy_archive(archive)
    handles.write_text("id,user_id,profile_id,makerspace_id,organization_id,handle,claimed_at,changed_at\n",
                       encoding="utf-8")
    assert not legacy_archive(archive)  # A current archive missing its page dataset is damage.
    handles.write_text("id,user_id,profile_id,handle,claimed_at,changed_at\n", encoding="utf-8")
    pages_csv.parent.mkdir(parents=True, exist_ok=True)
    pages_csv.write_text("id,makerspace_id,version,draft_revision_id,published_revision_id\n", encoding="utf-8")
    assert not legacy_archive(archive)
