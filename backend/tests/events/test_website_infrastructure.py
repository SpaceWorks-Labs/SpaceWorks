from tests.events.website_helpers import make_page, make_session
from datetime import datetime, time, timedelta, timezone as dt_timezone
from pathlib import Path

import pytest
from django.db import connection, transaction
from django.http import Http404
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from apps.events.models import EventSeries
from apps.events.models_website import EventPage, EventPageAsset, EventPageSection, EventSession
from apps.events.website_projection import window, project
from apps.makerspaces.website_origins import validate_origins
from apps.makerspaces import website_assets
from tests.events.website_helpers import website_fixture, grantee
from tests.events.collab_helpers import client_for
from tests.events.ticketing_helpers import event_space, open_event


@pytest.mark.parametrize("value", [["https://*.example"], ["http://example.test"], ["https://example.test/"],
    ["https://example.test/path"], ["https://example.test?x=1"], ["https://user@example.test"],
    ["https://example.test:443"], ["https://EXAMPLE.test"], ["https://example.test\nhttps://evil.test"],
    ["https://example.test#fragment"], ["https://example.test:*"], ["https://example.test" ] * 21, "https://example.test"])
def test_exact_https_embed_origins_fail_closed(value):
    with pytest.raises(ValidationError): validate_origins(value)


def test_exact_origins_are_deduplicated_and_nondefault_port_preserved():
    assert validate_origins(["https://example.test", "https://example.test", "https://other.test:8443"]) == ["https://example.test", "https://other.test:8443"]


@pytest.mark.django_db(transaction=True)
def test_shared_embed_route_no_longer_serves_events():
    # Owner decision #143: events embed only through L1's card with its EventEmbedPolicy;
    # the shared website-embed route refuses the events kind even with origins allowed.
    space, _, event, _, _ = website_fixture()
    assert space.website_embed_origins
    assert APIClient().get(f"/embed/{space.slug}/events/{event.public_token}/").status_code == 404


@pytest.mark.django_db(transaction=True)
def test_embed_settings_tenant_authority_origin_scope_and_audit():
    space, manager, event, _, _ = website_fixture()
    user, _ = grantee(space, event, "edit_details")
    route = f"/api/v1/admin/makerspaces/{space.pk}/website-embed-origins/"
    assert client_for(user).put(route, {"origins": []}, format="json").status_code in (403, 404)
    assert client_for(manager).put(route, {"origins": ["https://example.test/path"]}, format="json").status_code == 400
    response = client_for(manager).put(route, {"origins": ["https://example.test"]}, format="json")
    assert response.status_code == 200
    from apps.audit.models import AuditLog
    assert AuditLog.objects.filter(action="makerspace.website_origins_updated", makerspace=space).exists()
    foreign = event_space("other-origin")
    foreign.frontend_domain = "other-origin.example"; foreign.frontend_domain_status = "verified"
    foreign.save(update_fields=["frontend_domain", "frontend_domain_status"])
    assert client_for(manager).put(route, {"origins": []}, format="json", HTTP_ORIGIN="https://other-origin.example").status_code == 403


def test_all_spa_serving_configs_protect_fallback_and_proxy_embeds():
    root = Path(__file__).resolve().parents[3]
    nginx = (root / "frontend/nginx.conf").read_text()
    fallback = nginx.split("location = /index.html {", 1)[1].split("}", 1)[0]
    # Framing protection comes from the runtime include every SPA location shares
    # (frontend/docker-entrypoint.d/40-web-analytics.sh), not from inline add_header.
    assert "include /etc/nginx/analytics-headers.conf;" in fallback
    headers = (root / "frontend/docker-entrypoint.d/40-web-analytics.sh").read_text()
    assert 'X-Frame-Options "DENY" always' in headers
    assert "frame-ancestors 'none'" in headers
    embed = nginx.split("location /embed/ {", 1)[1].split("}", 1)[0]
    assert "proxy_pass http://backend:8000" in embed and "DENY" not in embed
    assert "/share/events/$event_share_token/" in nginx
    for name in ("Caddyfile", "Caddyfile.saas", "Caddyfile.saas-install"):
        text = (root / "deploy" / name).read_text()
        assert 'header_down X-Frame-Options "DENY"' in text
        assert "frame-ancestors 'none'" in text and "/embed/*" in text
        assert "/share/events/{re.event_card.2}/" in text


@pytest.mark.django_db(transaction=True)
def test_typed_retention_object_collection_and_events_purge(monkeypatch):
    space, _, event, page, speaker = website_fixture()
    asset = EventPageAsset.objects.create(page=page, object_key=f"events/website/{space.pk}/{page.pk}/image.webp", size_bytes=15, alt_text="Portrait")
    speaker.asset = asset; speaker.save(update_fields=["asset"])
    make_session(page=page, track=None, room=None, slug="talk", title="Talk",
        starts_at=event.starts_at, ends_at=event.ends_at)
    from apps.data_export.classification import EXPORTED_MODEL_FIELDS
    from apps.data_export.datasets import DATASET_SPECS
    from apps.tenant_migration.target_projection import TARGET_FIELD_PROJECTION
    from apps.tenant_migration.tenant_dump_catalog import validate_catalog
    from apps.tenant_migration.projection_guards import validate_unique_constraint_risks
    from apps.backup.object_ownership_registry import validate_object_reference_registry
    from apps.makerspaces.storage_key_collectors import collect_private_object_keys
    from apps.makerspaces.module_purge_collectors_events import events_delete
    for label in ("events.EventPage", "events.EventPageAsset", "events.EventPageSection", "events.EventSession", "events.EventSessionSpeaker"):
        assert label in EXPORTED_MODEL_FIELDS and label in DATASET_SPECS
    assert {"tagline", "accent_color", "section_order", "section_enabled", "venue"} <= set(
        EXPORTED_MODEL_FIELDS["events.EventPage"].split())
    assert {"headline", "organization", "website_url", "linkedin_url", "x_url", "sponsor_tier", "icon"} <= set(
        EXPORTED_MODEL_FIELDS["events.EventPageSection"].split())
    validate_catalog(); validate_unique_constraint_risks(); validate_object_reference_registry()
    assert asset.object_key in collect_private_object_keys(space)
    assert TARGET_FIELD_PROJECTION[("events.EventPage", "released")].value is False
    assert TARGET_FIELD_PROJECTION[("makerspaces.Makerspace", "website_embed_origins")].value == []
    other_space = event_space("unrelated-page"); other = open_event(other_space)
    survivor = make_page(makerspace=other_space, event=other)
    with transaction.atomic(), connection.cursor() as cursor:
        cursor.execute("SET LOCAL app.allow_immutable_delete = 'on'")
        events_delete(space, cursor)
    assert not EventPageAsset.objects.filter(pk=asset.pk).exists()
    assert EventPage.objects.filter(pk=survivor.pk).exists()


@pytest.mark.django_db(transaction=True)
def test_portable_ownership_survives_colliding_two_hop_import_keys():
    from apps.tenant_migration.models_import_job import TenantImportJob
    from apps.tenant_migration.models_import_objects import TenantImportObject
    space, _, _, page, _ = website_fixture()
    for n, source in enumerate(("events/website/100/200/image.webp", "migrated-objects/old-job/opaque")):
        job = TenantImportJob.objects.create(target_makerspace=space, expires_at=timezone.now() + timedelta(days=1))
        key = f"migrated-objects/{job.pk}/opaque"
        TenantImportObject.objects.create(job=job, bucket_kind="private", source_key=source,
            target_key=key, staging_key=f"tenant-imports/{job.pk}/staging", size=15, sha256="a" * 64, state="verified")
        asset = EventPageAsset.objects.create(page=page, object_key=key, size_bytes=15, alt_text="Imported")
        assert website_assets.owns(key, "events", space.pk, page.pk, asset=asset)
        assert not website_assets.owns(key, "events", space.pk + 100, page.pk, asset=asset)
        assert not website_assets.owns(key, "bookings", space.pk, page.pk, asset=asset)


def test_series_window_uses_elapsed_duration_across_fall_back():
    series = EventSeries(recurrence_timezone="America/New_York", dtstart_local_date=datetime(2026, 11, 1).date(),
        dtstart_local_time=time(1, 30), duration_minutes=60)
    start, end = window(series)
    assert start == datetime(2026, 11, 1, 5, 30, tzinfo=dt_timezone.utc)
    assert end - start == timedelta(hours=1)


def test_shared_website_modules_do_not_import_events_or_bookings():
    import ast
    root = Path(__file__).resolve().parents[2] / "apps/makerspaces"
    for path in root.glob("website_*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.ImportFrom):
                assert not (node.module or "").startswith(("apps.events", "apps.bookings")), path


def test_multipart_ingress_refuses_oversized_requests_and_cumulative_chunks():
    from rest_framework.exceptions import ParseError
    from apps.makerspaces.website_uploads import WebsiteUploadLimit
    handler = WebsiteUploadLimit()
    with pytest.raises(ParseError):
        handler.handle_raw_input(None, {}, website_assets.MAX_BYTES + 65537, b"boundary")
    handler.handle_raw_input(None, {}, None, b"boundary")
    assert handler.receive_data_chunk(b"x" * website_assets.MAX_BYTES, 0)
    with pytest.raises(ParseError):
        handler.receive_data_chunk(b"x", website_assets.MAX_BYTES)


def test_website_audit_emitters_are_covered_by_the_presentation_guard():
    from apps.audit.presentation_guards import presentation_catalog_errors
    assert presentation_catalog_errors() == []
