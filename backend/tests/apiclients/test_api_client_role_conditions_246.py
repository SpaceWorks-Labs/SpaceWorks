"""Decision 246: API-client management across every built-in role, anonymous callers and other spaces.

Authority is `manage_makerspace` (`api_client_views._visible_makerspace`). The expectation is derived from
`ROLE_CATALOG`, so a regrant is picked up without editing this file.
"""
import pytest
from rest_framework.test import APIClient

from apps.apiclients.models import ApiClient
from apps.makerspaces.role_catalog import ROLE_BY_SLUG, ROLE_CATALOG
from tests.fixed_roles.helpers import staff_account
from tests.return_helpers import authenticated_client, make_space

pytestmark = pytest.mark.django_db
SLUGS = [role.slug for role in ROLE_CATALOG]


def _urls(space):
    base = f"/api/v1/admin/makerspace/{space.pk}"
    return f"{base}/api-clients", f"{base}/api-client-scopes"


@pytest.mark.parametrize("slug", SLUGS)
def test_listing_and_creating_clients_follow_manage_makerspace(slug):
    space = make_space(f"acr-{slug}".replace("_", "-"))
    actor = staff_account(space, f"acr-actor-{slug}", slug)
    allowed = "manage_makerspace" in ROLE_BY_SLUG[slug].granted_actions
    clients_url, scopes_url = _urls(space)
    client = authenticated_client(actor)
    listed = client.get(clients_url)
    catalog = client.get(scopes_url)
    created = client.post(clients_url, {"name": f"client-{slug}", "scopes": []}, format="json")
    assert (listed.status_code == 200) is allowed
    if not allowed:
        for refused in (listed, catalog, created):
            assert refused.status_code in (403, 404)
        assert not ApiClient.objects.exists()


def test_anonymous_is_refused_on_every_api_client_route():
    space = make_space("acr-anon")
    clients_url, scopes_url = _urls(space)
    anon = APIClient()
    for url in (clients_url, scopes_url):
        assert anon.get(url).status_code in (401, 403)
    assert anon.post(clients_url, {"name": "x"}, format="json").status_code in (401, 403)
    assert not ApiClient.objects.exists()


def test_a_manager_of_another_space_cannot_list_create_or_touch_this_spaces_clients():
    mine, theirs = make_space("acr-iso-a"), make_space("acr-iso-b")
    outsider = authenticated_client(staff_account(theirs, "acr-iso-outsider", "space_manager"))
    clients_url, _ = _urls(mine)
    assert outsider.get(clients_url).status_code in (403, 404)
    assert outsider.post(clients_url, {"name": "intruder", "scopes": []}, format="json").status_code in (403, 404)
    owned = ApiClient.objects.filter(makerspace=mine)
    assert not owned.exists()


@pytest.mark.parametrize("body", [{}, {"name": ""}, {"name": "x" * 500}, {"name": "ok", "scopes": "not-a-list"},
                                  {"name": "ok", "scopes": ["no.such.scope"]}])
def test_create_validation_rejects_bad_names_and_unknown_scopes(body):
    space = make_space("acr-valid")
    boss = authenticated_client(staff_account(space, "acr-valid-boss", "space_manager"))
    response = boss.post(_urls(space)[0], body, format="json")
    assert response.status_code == 400
    assert not ApiClient.objects.exists()
