"""Drive real HMAC middleware, scope registry and scoped read projections."""
import hashlib
import hmac
import time
from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone
from rest_framework.test import APIClient

from apps.apiclients.checks import check_scope_registry
from apps.apiclients.models import ApiClient as Client
from apps.apiclients.scope_grants import validate_grantable_scopes
from apps.apiclients.scope_registry import lookup, scope_allows
from apps.events.models import Event, EventCheckInEvent, EventRegistration
from tests.return_helpers import make_space, make_user

READ = ["events:read"]
PEOPLE = [*READ, "participants:read"]
ALL = [*PEOPLE, "participants:attendance:read"]


@pytest.fixture
def setup(settings):
    settings.API_CLIENT_AUTH_REQUIRED = False
    settings.APICLIENT_REQUIRE_NONCE = False
    settings.API_CLIENT_ENC_KEY = __import__("cryptography.fernet", fromlist=["Fernet"]).Fernet.generate_key().decode()
    space = make_space("lane-f-api")
    space.enabled_features = [*space.enabled_features, "events.api_read"]
    space.save(update_fields=["enabled_features"])
    now = timezone.now()
    event = Event.objects.create(makerspace=space, title="Private event", starts_at=now,
                                 ends_at=now + timedelta(hours=2))
    return space, event


def issue(space, scopes=ALL):
    return Client.issue(label="Staff integration", scopes=scopes, makerspace=space,
                        client_type="server", allowed_origins=["https://integration.example"])


def read(client, secret, path, method="GET"):
    timestamp = str(int(time.time()))
    message = b"\n".join([method.encode(), path.encode(), timestamp.encode(), b""])
    signature = hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()
    return APIClient().generic(method, path, HTTP_X_CLIENT_ID=client.client_id,
                               HTTP_X_TIMESTAMP=timestamp, HTTP_X_SIGNATURE=signature)


def person(event, n=1, status="registered"):
    return EventRegistration.objects.create(event=event, name=f"Display {n}",
        email=f"private{n}@example.org", phone="secret phone", custom_answers={"private": "answer"},
        status=status)


@pytest.mark.django_db
def test_mandatory_even_when_rollout_disabled_and_no_jwt_bypass(setup):
    _, event = setup
    assert APIClient().get("/api/v1/events/").status_code == 401
    user = make_user("api-user")
    browser = APIClient()
    browser.force_authenticate(user)
    assert browser.get(f"/api/v1/events/{event.pk}/").status_code == 401


@pytest.mark.django_db
def test_event_and_participant_allowlists_and_attendance(setup):
    space, event = setup
    row = person(event, status="attended")
    EventCheckInEvent.objects.create(makerspace=space, event=event, registration=row,
                                     source="legacy", attended_at=timezone.now())
    client, secret = issue(space, PEOPLE)
    path = f"/api/v1/events/{event.pk}/participants/"
    response = read(client, secret, path)
    assert response.status_code == 200
    assert set(response.data["results"][0]) == {"id", "display_name", "registered_at"}
    client.scopes = ALL
    client.save(update_fields=["scopes"])
    response = read(client, secret, path)
    assert response.data["results"][0]["attended_at"]
    assert not any(value in str(response.data) for value in [row.email, row.phone,
                    str(row.checkin_token), "custom_answers", "payment", "answer"])
    detail = read(client, secret, f"/api/v1/events/{event.pk}/")
    assert set(detail.data) == {"id", "title", "status", "starts_at", "ends_at", "location", "is_public", "listing"}
    row.status = "registered"
    row.save(update_fields=["status"])
    assert read(client, secret, path).data["results"][0]["attended_at"] is None


@pytest.mark.django_db
@pytest.mark.parametrize("scopes", [["legacy:v1"], ["public:*"], READ,
    ["participants:read"], ["participants:attendance:read"]])
def test_participants_need_explicit_scope_conjunction(setup, scopes):
    space, event = setup
    client, secret = issue(space, ALL)
    Client.objects.filter(pk=client.pk).update(scopes=scopes)
    assert read(client, secret, f"/api/v1/events/{event.pk}/participants/").status_code == 401


@pytest.mark.django_db
def test_client_types_global_binding_wrong_tenant_and_missing_targets(setup):
    space, event = setup
    client, secret = issue(space)
    path = f"/api/v1/events/{event.pk}/"
    for changes in ({"client_type": "browser"}, {"makerspace": None}):
        Client.objects.filter(pk=client.pk).update(**changes)
        assert read(client, secret, path).status_code == 401
        Client.objects.filter(pk=client.pk).update(client_type="server", makerspace=space)
    other = make_space("lane-f-api-other")
    Client.objects.filter(pk=client.pk).update(makerspace=other)
    assert read(client, secret, path).status_code == 401
    assert read(client, secret, "/api/v1/events/99999999/").status_code == 401
    assert read(client, secret, "/api/v1/events/unknown/").status_code == 401


@pytest.mark.django_db
@pytest.mark.parametrize("change", ["archived", "module", "feature", "inactive"])
def test_live_tenant_module_feature_and_client_revocation(setup, change):
    space, event = setup
    client, secret = issue(space)
    if change == "archived":
        space.archived_at = timezone.now()
    elif change == "module":
        space.enabled_modules = [x for x in space.enabled_modules if x != "events"]
    elif change == "feature":
        space.enabled_features = [x for x in space.enabled_features if x != "events.api_read"]
    else:
        Client.objects.filter(pk=client.pk).update(is_active=False)
    space.save()
    assert read(client, secret, f"/api/v1/events/{event.pk}/").status_code in (401, 403, 404)


@pytest.mark.django_db
def test_keyset_has_no_duplicates_and_rejects_cross_subject_cursor(setup):
    space, event = setup
    for n in range(4):
        person(event, n)
    client, secret = issue(space)
    path = f"/api/v1/events/{event.pk}/participants/"
    response = read(client, secret, path + "?page_size=2")
    cursor = response.data["next_cursor"]
    next_page = read(client, secret, path + "?page_size=2&cursor=" + cursor)
    assert next_page.status_code == 200
    assert next_page.data["next_cursor"] is None
    ids = [r["id"] for r in response.data["results"] + next_page.data["results"]]
    assert len(set(ids)) == 4
    assert read(client, secret, "/api/v1/events/?cursor=" + cursor).status_code == 400
    assert read(client, secret, path + "?cursor=forged").status_code == 400
    for size in ("0", "201", "nonsense"):
        assert read(client, secret, path + "?page_size=" + size).status_code == 400
    other, key = issue(space)
    assert read(other, key, path + "?cursor=" + cursor).status_code == 400


@pytest.mark.django_db
def test_head_and_read_cache_policy_and_no_mutation_methods(setup):
    space, event = setup
    client, secret = issue(space)
    for path in ("/api/v1/events/", f"/api/v1/events/{event.pk}/",
                 f"/api/v1/events/{event.pk}/participants/"):
        response = read(client, secret, path, "HEAD")
        assert response.status_code == 200
        assert response.content == b""
        assert response["Cache-Control"] == "private, no-store"
        assert read(client, secret, path, "POST").status_code == 401


def test_registry_and_grant_policy():
    for name in ("integration-event-list", "integration-event-detail", "integration-event-participants"):
        for method in ("GET", "HEAD"):
            entry = lookup(name, method)
            assert entry and not entry.legacy_v1 and entry.server_only and entry.tenant_bound
            assert not scope_allows(entry, ["legacy:v1"])
    with pytest.raises(ValueError):
        validate_grantable_scopes(ALL, privileged=False)
    with pytest.raises(ValueError):
        validate_grantable_scopes(["participants:read"], privileged=True)
    assert validate_grantable_scopes(ALL, privileged=True) == ALL
    assert check_scope_registry(app_configs=None) == []


@pytest.mark.django_db
def test_staff_scopes_cannot_be_issued_as_global_or_browser(setup):
    space, _ = setup
    for tenant, kind in ((None, "server"), (space, "browser")):
        with pytest.raises(ValidationError):
            Client.issue(label="Forbidden", scopes=ALL, makerspace=tenant,
                         client_type=kind, allowed_origins=["https://integration.example"])


@pytest.mark.django_db
def test_participant_projection_reads_encrypted_name_via_accessor(setup):
    from django.db import connection
    from tests.encryption.conftest import enabled_encryption
    space, event = setup
    client, secret = issue(space, PEOPLE)
    with enabled_encryption():
        row = person(event)
        with connection.cursor() as cursor:
            cursor.execute("SELECT name FROM events_eventregistration WHERE id=%s", [row.pk])
            assert cursor.fetchone()[0] != "Display 1"
        result = read(client, secret, f"/api/v1/events/{event.pk}/participants/")
        assert result.status_code == 200
        assert result.data["results"][0]["display_name"] == "Display 1"


@pytest.mark.django_db(transaction=True)
def test_audited_participant_reads_respect_source_freeze(setup):
    from apps.audit.models import AuditLog
    from tests.tenant_migration.source_gate_helpers import close_gate, make_actor
    space, event = setup
    person(event)
    client, secret = issue(space)
    close_gate(space, make_actor("api-read-freeze"))
    result = read(client, secret, f"/api/v1/events/{event.pk}/participants/")
    assert result.status_code == 423
    assert not AuditLog.objects.filter(action="api_client.participants_read").exists()


@pytest.mark.django_db
def test_subject_target_adapter_is_registered_for_origin_resolution(setup):
    from django.test import RequestFactory
    from django.urls import resolve
    from apps.makerspaces.origin_scope_routes import authoritative_route_resolution
    space, event = setup
    client, _ = issue(space)
    for path in ("/api/v1/events/", f"/api/v1/events/{event.pk}/"):
        req = RequestFactory().get(path, HTTP_X_CLIENT_ID=client.client_id)
        req.resolver_match = resolve(path)
        assert authoritative_route_resolution(req) == ({space.pk}, True)
