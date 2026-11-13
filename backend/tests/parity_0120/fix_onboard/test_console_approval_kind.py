"""FIX-ONBOARD: the console approve route honours the request's kind (decision 295), the
list filters on requested_kind, and the public card verify names the issuer's noun."""
import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from apps.card_designs import tokens
from apps.makerspaces import member_card_services as services
from apps.makerspaces.models import Makerspace, MemberCardSettings
from apps.makerspaces.space_kind import ORGANIZATION_AREAS
from tests.hosting_requests.helpers import public_row
from tests.l3_local.helpers import card_space, manager, member
from tests.r2_superadmin_local.helpers import api, superadmin

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("managed")]
BASE = "/api/v1/admin/platform/hosting-requests"


def test_approving_an_organization_request_creates_an_organization_workspace(django_capture_on_commit_callbacks):
    row, _ = public_row(requested_kind="organization", proposed_slug="chess-society", space_name="Chess Society")
    with django_capture_on_commit_callbacks(execute=True):
        response = api(superadmin()).post(f"{BASE}/{row.pk}/approve", {"invite_manager": False}, format="json")
    assert response.status_code == 200, response.content
    space = Makerspace.objects.get(pk=response.json()["makerspace"]["id"])
    assert space.kind == "organization"
    assert response.json()["request"]["requested_kind"] == "organization"
    modules = set(space.enabled_modules or [])
    assert "inventory" not in modules and "machines" not in modules
    assert modules, ORGANIZATION_AREAS  # the workspace defaults were applied, not the registry's


def test_approving_a_makerspace_request_stays_a_makerspace():
    row, _ = public_row()
    response = api(superadmin()).post(f"{BASE}/{row.pk}/approve", {"invite_manager": False}, format="json")
    assert response.status_code == 200, response.content
    assert Makerspace.objects.get(pk=response.json()["makerspace"]["id"]).kind == "makerspace"


def test_a_body_kind_that_disagrees_with_the_request_is_a_400_and_rolls_back():
    row, _ = public_row(requested_kind="organization")
    response = api(superadmin()).post(f"{BASE}/{row.pk}/approve", {"kind": "makerspace"}, format="json")
    assert response.status_code == 400
    row.refresh_from_db()
    assert row.status == "submitted" and row.created_makerspace_id is None
    ok = api(superadmin("root-2")).post(f"{BASE}/{row.pk}/approve", {"kind": "organization", "invite_manager": False},
                                        format="json")
    assert ok.status_code == 200, ok.content


def test_list_filters_by_requested_kind_and_rejects_a_bad_value():
    public_row(applicant_email="a@example.test")
    org, _ = public_row(requested_kind="organization", applicant_email="b@example.test")
    root = api(superadmin())
    rows = root.get(BASE, {"requested_kind": "organization"}).json()["results"]
    assert [r["id"] for r in rows] == [org.pk] and rows[0]["requested_kind"] == "organization"
    assert root.get(BASE, {"requested_kind": "makerspace"}).json()["count"] == 1
    assert root.get(BASE, {"requested_kind": "club"}).status_code == 400


@pytest.mark.parametrize("kind,noun", [("makerspace", "makerspace"), ("organization", "organization")])
def test_verify_issuer_names_the_space_noun(kind, noun):
    space = card_space(f"fo-verify-{kind}")
    Makerspace.objects.filter(pk=space.pk).update(kind=kind)
    MemberCardSettings.objects.update_or_create(makerspace=space, defaults={"public_verify": True})
    card = services.issue_card(manager(space), member(space)[1])
    cache.clear()
    response = APIClient(HTTP_HOST="localhost").get(f"/api/v1/public/card-verifications/{tokens.live('member_card', card).token}")
    assert response.status_code == 200, response.content
    issuer = response.json()["issuer"]
    assert issuer["kind"] == "space" and issuer["space_noun"] == noun
    assert set(issuer) == {"kind", "name", "logo_url", "space_noun"}
