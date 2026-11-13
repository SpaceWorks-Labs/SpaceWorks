"""Upload authorization, actual throttle scope, CORS, and OpenAPI contracts."""

import io
from types import SimpleNamespace

import pytest
from django.urls import path, reverse
from drf_spectacular.generators import SchemaGenerator
from rest_framework.exceptions import ParseError
from rest_framework.throttling import ScopedRateThrottle

from apps.accounts.models import User
from apps.backup.settings_policy import ENV_SURFACE
from apps.tenant_migration import import_chunk_parser
from apps.tenant_migration.views_import_upload import (
    TenantImportArchiveChunkView, TenantImportArchiveCompleteView, TenantImportUploadStartView,
)
from tests.tenant_migration.test_import_async_staging import actor, client_for, ops_dir
from tests.tenant_migration.test_import_chunked_upload import chunk, complete, start, uploading_job

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("length,body", [
    (None, b"x"), ("", b"x"), ("invalid", b"x"), ("-1", b"x"),
    ("0", b""), ("5", b"12345"), ("2", b"x"),
])
def test_parser_itself_rejects_missing_invalid_oversized_or_short_length(monkeypatch, length, body):
    monkeypatch.setattr(import_chunk_parser, "CHUNK_MAX_BYTES", 4)
    request = SimpleNamespace(META={} if length is None else {"CONTENT_LENGTH": length})
    with pytest.raises(ParseError):
        import_chunk_parser.OffsetChunkParser().parse(
            io.BytesIO(body), parser_context={"request": request},
        )


def test_parser_never_reads_past_declared_length(monkeypatch):
    monkeypatch.setattr(import_chunk_parser, "CHUNK_MAX_BYTES", 4)
    stream = io.BytesIO(b"1234unread")
    parsed = import_chunk_parser.OffsetChunkParser().parse(
        stream, parser_context={"request": SimpleNamespace(META={"CONTENT_LENGTH": "4"})},
    )
    assert parsed == b"1234"
    assert stream.tell() == 4


@pytest.mark.parametrize("operation", ["start", "chunk", "complete"])
def test_non_superadmin_is_forbidden_on_every_upload_route(uploading_job, operation):
    client = client_for(User.objects.create_user(username="upload-member", access_status="active"))
    if operation == "start":
        response = start(client)
    elif operation == "chunk":
        response = chunk(client, uploading_job, b"x")
    else:
        response = complete(client, uploading_job)
    assert response.status_code == 403
    uploading_job.refresh_from_db()
    assert uploading_job.upload_received_bytes == 0
    assert uploading_job.status == "uploading"


def test_patch_uses_upload_scope_in_actual_throttle_check(actor, uploading_job, monkeypatch):
    scopes = []
    original = ScopedRateThrottle.allow_request

    def observe(throttle, request, view):
        scopes.append(view.throttle_scope)
        return original(throttle, request, view)

    monkeypatch.setattr(ScopedRateThrottle, "allow_request", observe)
    assert chunk(client_for(actor), uploading_job, b"x").status_code == 200
    assert scopes == ["tenant_migration_upload"]


def test_upload_offset_is_allowed_by_real_cors_preflight(actor, uploading_job, settings):
    origin = "https://upload.example.test"
    settings.CORS_ALLOWED_ORIGINS = [origin]
    response = client_for(actor).options(
        reverse("tenant-migration-import-archive-chunk", args=(uploading_job.pk,)),
        HTTP_ORIGIN=origin,
        HTTP_ACCESS_CONTROL_REQUEST_METHOD="PATCH",
        HTTP_ACCESS_CONTROL_REQUEST_HEADERS="content-type, upload-offset",
    )
    assert response.status_code == 200
    assert response["Access-Control-Allow-Origin"] == origin
    allowed = {header.strip().lower() for header in response["Access-Control-Allow-Headers"].split(",")}
    assert {"content-type", "upload-offset"} <= allowed
    assert "PATCH" in response["Access-Control-Allow-Methods"]


def test_upload_throttle_is_in_environment_surface(settings):
    assert "THROTTLE_TENANT_MIGRATION_UPLOAD" in ENV_SURFACE
    assert "tenant_migration_upload" in settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]


def test_openapi_documents_all_upload_methods_and_binary_contract():
    base = "api/v1/admin/platform/tenant-migrations/imports"
    schema = SchemaGenerator(patterns=[
        path(f"{base}/uploads", TenantImportUploadStartView.as_view()),
        path(f"{base}/<uuid:job_id>/archive", TenantImportArchiveChunkView.as_view()),
        path(f"{base}/<uuid:job_id>/archive/complete", TenantImportArchiveCompleteView.as_view()),
    ]).get_schema(request=None, public=True)
    routes = schema["paths"]
    for suffix, method, success in (("/uploads", "post", "201"),
                                    ("/{job_id}/archive", "patch", "200"),
                                    ("/{job_id}/archive/complete", "post", "202")):
        operation = routes[f"/{base}{suffix}"][method]
        assert operation["security"]
        assert {success, "403", "429"} <= set(operation["responses"])
        assert operation["responses"][success]["content"]["application/json"]["schema"]
    patch = routes[f"/{base}/{{job_id}}/archive"]["patch"]
    assert patch["requestBody"]["content"]["application/offset+octet-stream"]["schema"] == {
        "type": "string", "format": "binary",
    }
    headers = {p["name"]: p for p in patch["parameters"] if p["in"] == "header"}
    assert headers["Upload-Offset"]["required"]
    assert headers["Content-Length"]["required"]
    assert {"400", "404", "409", "415", "429"} <= set(patch["responses"])
    conflict = patch["responses"]["409"]["content"]["application/json"]["schema"]
    properties = schema["components"]["schemas"][conflict["$ref"].rsplit("/", 1)[-1]]["properties"]
    assert properties["upload_received_bytes"]["type"] == "integer"
