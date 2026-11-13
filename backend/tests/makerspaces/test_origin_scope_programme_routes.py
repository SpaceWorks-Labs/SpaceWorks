"""The event programme's staff routes carry their event's makerspace into the web origin scope (MOB-STAFF).

A custom-origin staff session of space A must not reach an event of space B through a programme admin route;
its own space's event is accepted; the platform origin (no staff origin scope) is unaffected.
"""
from datetime import timedelta

import pytest
from django.test import RequestFactory
from django.urls import resolve
from django.utils import timezone

from apps.events.models import Event
from apps.makerspaces.models import Makerspace
from apps.makerspaces.origin_scope import staff_origin_scope_allows
from apps.makerspaces.origin_scope_routes import authoritative_route_resolution, request_route_targets

pytestmark = pytest.mark.django_db
ROUTES = ("/api/v1/admin/events/{pk}/tracks/", "/api/v1/admin/events/{pk}/judging-rounds/")


def _space(slug):
    return Makerspace.objects.create(
        name=slug, slug=slug, frontend_domain=f"{slug}.example.test",
        frontend_domain_status=Makerspace.DomainStatus.VERIFIED)


def _event(space):
    start = timezone.now() + timedelta(hours=1)
    return Event.objects.create(makerspace=space, title="Programme", starts_at=start, ends_at=start + timedelta(hours=1))


def _request(path, space=None):
    extra = {"HTTP_ORIGIN": f"https://{space.frontend_domain}"} if space else {}
    request = RequestFactory().get(path, **extra)
    request.resolver_match = resolve(path)
    return request


@pytest.mark.parametrize("template", ROUTES)
def test_custom_origin_staff_reaches_only_its_own_spaces_event(template):
    space_a, space_b = _space("prog-origin-a"), _space("prog-origin-b")
    own, foreign = _event(space_a), _event(space_b)
    assert staff_origin_scope_allows(_request(template.format(pk=own.pk), space_a)) is True
    assert staff_origin_scope_allows(_request(template.format(pk=foreign.pk), space_a)) is False
    assert staff_origin_scope_allows(_request(template.format(pk=987654), space_a)) is False


@pytest.mark.parametrize("template", ROUTES)
def test_programme_route_gives_the_source_gate_and_rls_a_target(template):
    event = _event(_space("prog-gate-a"))
    request = _request(template.format(pk=event.pk))
    assert request_route_targets(request)[1:] == ({event.makerspace_id}, False, True)
    assert authoritative_route_resolution(request) == ({event.makerspace_id}, True)


def test_platform_origin_without_a_staff_scope_is_unaffected():
    event = _event(_space("prog-platform-a"))
    assert staff_origin_scope_allows(_request(f"/api/v1/admin/events/{event.pk}/tracks/")) is True
