"""The staff 'present now' roster resolves its makerspace from the URL (a Space Manager got 403)."""
import pytest
from django.test import RequestFactory
from django.urls import resolve

from apps.makerspaces.origin_scope_routes import request_route_targets


@pytest.mark.django_db
def test_staff_presence_roster_resolves_its_makerspace_target():
    path = "/api/v1/admin/makerspace/4/presence-sessions/current"
    request = RequestFactory().get(f"{path}?page=1")
    request.resolver_match = resolve(path)
    assert request_route_targets(request) == ("admin-presence-sessions-current", {4}, False, True)
