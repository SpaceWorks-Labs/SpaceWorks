"""Handle kind, venue and browser scope remain independent admission checks."""

from types import SimpleNamespace

import pytest
from django.urls import resolve
from rest_framework.test import APIRequestFactory

from apps.apiclients.scope_registry import classify, lookup, resolve_target, target_allows
from apps.apiclients.scope_registry_public_pages import PublicHandleTarget
from apps.apiclients.scope_registry_routes import PUBLIC_READ
from apps.makerspaces import public_page_services as pages
from apps.makerspaces.models import Makerspace
from apps.makerspaces.origin_scope_routes import authoritative_route_resolution

pytestmark = pytest.mark.django_db(transaction=True)


def request(path, **headers):
    value = APIRequestFactory().get(path, HTTP_HOST="testserver", **headers)
    value.resolver_match = resolve(path)
    return value


def publish(space, actor):
    state = pages.change_handle("makerspace", space.pk, actor=actor, version=0, handle="route.lab")
    state = pages.save("makerspace", space.pk, actor=actor, version=state["version"], document=state["document"])
    return pages.publish("makerspace", space.pk, actor=actor, version=state["version"], draft_revision_id=state["draft_revision_id"])


def test_mixed_handle_resolves_a_tagged_tenant_and_never_an_unpublished_draft(page_owner):
    space, actor = page_owner
    state = publish(space, actor)
    req = request("/api/v1/public/page-handles/route.lab/")
    entry = lookup("public-page-handle", "GET")
    target, resolved = resolve_target(req, entry)
    assert isinstance(target, PublicHandleTarget) and target.kind == "tenant"
    assert resolved and target.pk == space.pk
    assert authoritative_route_resolution(req) == ({space.pk}, True)
    client = SimpleNamespace(makerspace_id=space.pk, scopes=[PUBLIC_READ])
    assert classify(req, client).verdict
    assert not target_allows(entry, SimpleNamespace(makerspace_id=space.pk + 1), target, True)
    pages.unpublish("makerspace", space.pk, actor=actor, version=state["version"])
    assert resolve_target(request(req.path), entry) == (None, False)


def test_global_handle_success_has_global_observation(monkeypatch):
    import apps.apiclients.scope_registry as registry
    monkeypatch.setattr(registry, "resolve_handle_target", lambda *_: (PublicHandleTarget("global"), True))
    observation = classify(request("/api/v1/public/page-handles/global.org/"),
                           SimpleNamespace(makerspace_id=7, scopes=[PUBLIC_READ]))
    assert observation.verdict and observation.target_resolution == "global"
    assert observation.target_resolved is True and observation.target_makerspace_id is None
    assert not target_allows(lookup("public-page-handle", "GET"),
                             SimpleNamespace(makerspace_id=7), None, False)


def test_live_global_handle_is_platform_hosted_with_recognized_tenant_browser_origin(page_owner):
    from django.db import transaction
    from django.utils import timezone
    from apps.organizations.models import Organization
    from apps.organizations.models_public_pages import OrganizationPublicPage, OrganizationPublicPageRevision
    from apps.makerspaces.models_profiles import PublicHandle
    from apps.makerspaces.public_page_contract import empty_document
    space, _ = page_owner
    space.frontend_domain = "tenant.example"
    space.frontend_domain_status = "verified"
    space.save(update_fields=["frontend_domain", "frontend_domain_status"])
    owner = Organization.objects.create(name="Global read", slug="global-read", public_profile_enabled=True)
    with transaction.atomic():
        page = OrganizationPublicPage.objects.create(organization=owner)
        revision = OrganizationPublicPageRevision.objects.create(page=page, document=empty_document("organization"))
        page.draft_revision = page.published_revision = revision
        page.save(update_fields=["draft_revision", "published_revision"])
        PublicHandle.objects.create(organization=owner, handle="live.global", changed_at=timezone.now())
    entry = lookup("public-page-handle", "GET")
    path = "/api/v1/public/page-handles/live.global/"
    target, resolved = resolve_target(request(path, HTTP_ORIGIN="https://tenant.example"), entry)
    assert resolved and target.kind == "global" and target.pk is None
    req = request(path)
    req.META["HTTP_HOST"] = "tenant.example"
    assert resolve_target(req, entry) == (None, False)


def test_short_event_is_targeted_to_venue(event_owner):
    space, _, event = event_owner
    req = request(f"/api/v1/public/event-codes/{event.public_token}/")
    target, resolved = resolve_target(req, lookup("public-event-code", "GET"))
    assert resolved and target.pk == space.pk
    assert authoritative_route_resolution(req) == ({space.pk}, True)
    other = Makerspace.objects.create(name="Foreign", slug="code-foreign", frontend_domain="foreign.example",
                                      frontend_domain_status="verified")
    conflicting = request(req.path, HTTP_ORIGIN=f"https://{other.frontend_domain}")
    assert resolve_target(conflicting, lookup("public-event-code", "GET")) == (None, False)


def test_global_editor_has_no_selected_tenant_fallback(page_owner):
    from apps.makerspaces.origin_scope import staff_origin_scope_allows
    req = request("/api/v1/admin/organizations/1/public-page/")
    req.selected_makerspace_id = page_owner[0].pk
    assert authoritative_route_resolution(req) == (set(), True)
    assert staff_origin_scope_allows(req)
    # HttpRequest.headers is cached: mutating META after the first check would
    # keep exercising the original request without an Origin header.
    req = request(req.path, HTTP_ORIGIN="https://unknown.example")
    req.selected_makerspace_id = page_owner[0].pk
    assert not staff_origin_scope_allows(req)
