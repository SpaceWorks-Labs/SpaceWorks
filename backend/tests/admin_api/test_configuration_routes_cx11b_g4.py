"""Closed notice and legal override endpoints retain exact copy through their policy switches."""
from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.makerspaces.models import Makerspace
from apps.operations.legal_pages import set_platform_page, set_space_override
from tests.modules.switch_matrix_object_helpers import object_world
from tests.operations.route_support_cx11b_g4 import cycle, outsider, send

pytestmark = [pytest.mark.django_db, pytest.mark.area_platform, pytest.mark.area_frontend_shell]


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("method", ["GET", "PUT"])
def test_closed_notice_route_effect_and_restoration(native, method):
    space, client, _ = object_world(native)
    space.public_closed_notice = "Retained maintenance notice"
    space.save(update_fields=["public_closed_notice"])
    day = timezone.localdate() + timedelta(days=7)
    url = reverse("admin-makerspace-public-closed-notice", kwargs={"makerspace_id": space.pk})
    body = {"public_closed_notice": "Reopens next week", "public_reopens_on": day.isoformat()}

    def check(response):
        stored = Makerspace.objects.get(pk=space.pk)
        expected = ("Reopens next week", day) if method == "PUT" else ("Retained maintenance notice", None)
        assert (stored.public_closed_notice, stored.public_reopens_on) == expected
        assert response.data == {"public_closed_notice": expected[0], "public_reopens_on": day.isoformat() if method == "PUT" else None}
    foreign = outsider(native)
    cycle(space, "public_site.closed_notice", lambda: send(client, method, url, body if method == "PUT" else {}), check,
          off=(404, "capability_disabled"), audit=("makerspace.closed_notice_updated",) if method == "PUT" else (),
          foreign=lambda: send(foreign, method, url, body if method == "PUT" else {}), foreign_native=native)


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("name,method", [("admin-makerspace-legal-page", "GET"),
    ("admin-makerspace-legal-page", "PUT"), ("public-legal-page", "GET")])
def test_legal_page_route_effect_and_fallback_are_exact(native, name, method):
    space, client, _ = object_world(native)
    set_platform_page("terms", "", "# Retained platform terms")
    set_space_override(space, "terms", "# Retained tenant terms")
    public = name == "public-legal-page"
    url = reverse(name, kwargs={"page": "terms"} if public else {"makerspace_id": space.pk, "slug": "terms"})
    if public:
        url += f"?space={space.slug}"
    body = {"markdown": "# Changed tenant terms"} if method == "PUT" else {}

    def check(response):
        expected = "# Changed tenant terms" if method == "PUT" else "# Retained tenant terms"
        assert (response.data["source"], response.data["markdown"]) == ("space", expected)
        assert Makerspace.objects.get(pk=space.pk).branding_config["legal_pages"]["terms"] == expected

    def off_check(response):
        assert Makerspace.objects.get(pk=space.pk).branding_config["legal_pages"]["terms"] == "# Retained tenant terms"
        if method == "GET":
            assert (response.data["source"], response.data["markdown"]) == ("platform", "# Retained platform terms")
    foreign = APIClient() if public else outsider(native)
    # Public terms are anonymous; staff editors use 481/494. The GET policy falls back,
    # while PUT disappears: existing legal.space_pages contract, not a blanket refusal.
    cycle(space, "legal.space_pages", lambda: send(client, method, url, body), check,
          off=(404, "not_found") if method == "PUT" else (200, None), off_check=off_check,
          audit=("makerspace.legal_page_updated",) if method == "PUT" else (),
          foreign=lambda: send(foreign, method, url, body), foreign_pair=(200, None) if public else (404, "not_found"), foreign_native=native and not public)
