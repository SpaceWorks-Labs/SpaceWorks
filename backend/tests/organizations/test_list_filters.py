"""Owner picker listing exposes status and filters name/slug without case sensitivity."""
import pytest

from tests.organizations.test_admin_create_link import BASE, superadmin
from tests.organizations.test_org_authority import make_organization
from tests.organizations.test_org_console_access import client_for

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("active", [None, "true", "false"])
def test_list_exposes_active_status_and_filters_it(active):
    enabled = make_organization("enabled")
    disabled = make_organization("disabled", is_active=False)
    response = client_for(superadmin()).get(BASE, {} if active is None else {"active": active})
    assert response.status_code == 200, response.data
    expected = {enabled.pk: True, disabled.pk: False}
    if active is not None:
        expected = {key: value for key, value in expected.items() if value == (active == "true")}
    assert {row["id"]: row["is_active"] for row in response.data["results"]} == expected
    assert response.data["count"] == len(expected)


@pytest.mark.parametrize("search", ["UNITY", "EEDLE"])
def test_search_matches_case_insensitive_substrings_of_name_or_slug(search):
    match = make_organization("needle-network")
    match.name = "Community Workshop"
    match.save(update_fields=["name"])
    make_organization("unrelated")
    response = client_for(superadmin()).get(BASE, {"search": search})
    assert response.status_code == 200, response.data
    assert [row["id"] for row in response.data["results"]] == [match.pk]


def test_search_and_active_filters_are_combined():
    match = make_organization("shared-active")
    make_organization("shared-inactive", is_active=False)
    make_organization("unrelated")
    response = client_for(superadmin()).get(BASE, {"search": "shared", "active": "true"})
    assert response.status_code == 200, response.data
    assert [row["id"] for row in response.data["results"]] == [match.pk]


def test_invalid_active_filter_is_a_field_error():
    response = client_for(superadmin()).get(BASE, {"active": "bogus"})
    assert response.status_code == 400 and "active" in response.data
