"""Public RBAC and account-context regression cases for decisions 494/499."""
from types import SimpleNamespace

import pytest
from django.contrib.auth.models import AnonymousUser
from rest_framework.response import Response
from rest_framework.test import APIClient

from apps.accounts import rbac
from apps.accounts.tenant_refusal import has_standing, outsider_refusal
from apps.accounts.tokens import SpaceWorksRefreshToken
from apps.makerspaces.models import Makerspace
from tests.accounts.account_factories import make_membership, make_staff
from tests.accounts.ua1_helpers import person, platform
from apps.makerspaces.servability import request_scope

pytestmark = pytest.mark.django_db


@pytest.fixture
def scope_setup():
    home = Makerspace.objects.create(name="Scope home", slug="cx6-scope-home")
    away = Makerspace.objects.create(name="Scope away", slug="cx6-scope-away")
    actor = make_staff(home, username="cx6-scope-manager", role_slug="inventory_manager")
    return actor, home, away


@pytest.mark.parametrize("actor", [None, AnonymousUser()])
def test_non_principals_have_no_scope_or_actions(actor):
    assert rbac.resolve_scope(actor) == set()
    assert rbac.effective_actions(actor, 1) == set()
    assert rbac.makerspaces_for_action(actor, rbac.Action.EDIT_INVENTORY) == set()
    assert rbac.can(actor, rbac.Action.EDIT_INVENTORY, 1) is False
    assert rbac.is_space_manager_identity(actor, 1) is False
    assert list(rbac.scope_by_visibility_or_action(actor, rbac.Action.EDIT_INVENTORY,
                                                 Makerspace.objects.all(), field="pk")) == []


def test_visibility_does_not_grant_an_action_and_scope_union_is_exact(scope_setup):
    actor, home, away = scope_setup
    make_membership(actor, away)
    assert has_standing(actor, away.pk) is True
    assert rbac.can(actor, rbac.Action.EDIT_INVENTORY, away.pk) is False
    assert rbac.can(actor, rbac.Action.EDIT_INVENTORY) is False
    assert rbac.makerspaces_for_actions(actor, rbac.Action.EDIT_INVENTORY,
                                       rbac.Action.MANAGE_EVENTS) == {home.pk}
    assert set(rbac.scope_by_visibility_or_action(actor, rbac.Action.EDIT_INVENTORY,
               Makerspace.objects.all(), field="pk").values_list("pk", flat=True)) == {home.pk, away.pk}
    assert list(rbac.scope_by_action(actor, rbac.Action.MANAGE_EVENTS,
                                    Makerspace.objects.all(), field="pk")) == []
    assert list(rbac.scope_by_action(actor, rbac.Action.EDIT_INVENTORY,
               Makerspace.objects.all(), field="pk").values_list("pk", flat=True)) == [home.pk]


@pytest.mark.parametrize("bad", [True, False, 0, -1, "1", 1.5])
def test_scheduler_requires_a_persisted_integer_scope(scope_setup, bad):
    with pytest.raises(ValueError) as error:
        rbac.scope_for_scheduled_work(Makerspace.objects.all(), makerspace_id=bad, field="pk")
    assert str(error.value) == "Scheduled work requires a persisted makerspace id."


def test_scheduler_explicit_scope_cannot_include_another_tenant(scope_setup):
    _, home, away = scope_setup
    rows = rbac.scope_for_scheduled_work(Makerspace.objects.all(), makerspace_id=home.pk, field="pk")
    assert list(rows.values_list("pk", flat=True)) == [home.pk]
    assert rows.filter(pk=away.pk).count() == 0


def test_superadmin_global_scope_and_union_become_explicit_when_a_tenant_is_paused(scope_setup):
    _, home, away = scope_setup
    root = platform("cx6-scope-root")
    with request_scope():
        assert rbac.resolve_scope(root) is rbac.ALL
        assert rbac.makerspaces_for_actions(root, rbac.Action.EDIT_INVENTORY, rbac.Action.MANAGE_EVENTS) is rbac.ALL
        original = Makerspace.objects.all()
        assert rbac.scope_by_makerspace(root, original, "pk") is original
        assert rbac.scope_by_action(root, rbac.Action.EDIT_INVENTORY, original, field="pk") is original
        Makerspace.objects.filter(pk=away.pk).update(lifecycle_state="suspended")
        assert rbac.resolve_scope(root) == {home.pk}
        assert rbac.effective_actions(root, away.pk) == set()
        assert rbac.can(root, rbac.Action.EDIT_INVENTORY, away.pk) is False
        assert rbac.is_space_manager_identity(root, away.pk) is False
        assert rbac.makerspaces_for_actions(root, rbac.Action.EDIT_INVENTORY, rbac.Action.MANAGE_EVENTS) == {home.pk}
        assert list(rbac.scope_for_scheduled_work(Makerspace.objects.all(), field="pk").values_list("pk", flat=True)) == [home.pk]


def _context(actor, space_id, *, path="/api/v1/admin/example", kwargs=None):
    request = SimpleNamespace(_user=actor, path=path,
        resolver_match=SimpleNamespace(url_name="cx6-unknown", kwargs={"makerspace_id": space_id}))
    return {"request": request, "view": SimpleNamespace(kwargs=kwargs or {})}


@pytest.mark.parametrize("status", [400, 402, 403, 404, 406, 409, 410, 422])
def test_every_id_dependent_outsider_refusal_is_identical(scope_setup, status):
    actor, _, away = scope_setup
    response = outsider_refusal(Response({"code": "sensitive", "detail": "tenant detail"}, status=status),
                                _context(actor, away.pk))
    assert response.status_code == 404
    assert response.data == {"detail": "Not found.", "code": "not_found"}
    assert response.framework_code is True


@pytest.mark.parametrize("status", [200, 302, 401, 405, 429, 500])
def test_id_independent_answers_are_preserved(scope_setup, status):
    actor, _, away = scope_setup
    original = Response({"code": "original"}, status=status)
    assert outsider_refusal(original, _context(actor, away.pk)) is original
    assert original.status_code == status
    assert original.data == {"code": "original"}


@pytest.mark.parametrize("path", ["/api/v1/public/example", "/api/v1/auth/example"])
def test_public_and_account_routes_do_not_use_staff_refusal(scope_setup, path):
    actor, _, away = scope_setup
    original = Response({"code": "permission_denied"}, status=403)
    assert outsider_refusal(original, _context(actor, away.pk, path=path)) is original


@pytest.mark.parametrize("identifier", [None, "bad", 0, -1])
def test_no_valid_path_scope_preserves_original_refusal(scope_setup, identifier):
    actor, _, _ = scope_setup
    original = Response({"code": "validation_error"}, status=400)
    assert outsider_refusal(original, _context(actor, identifier)) is original


def test_member_keeps_module_disabled_and_local_permission_denied(scope_setup):
    actor, _, away = scope_setup
    make_membership(actor, away)
    for status, code in [(404, "module_disabled"), (403, "permission_denied")]:
        original = Response({"code": code}, status=status)
        assert outsider_refusal(original, _context(actor, away.pk)) is original
        assert (original.status_code, original.data["code"]) == (status, code)


def test_view_kwargs_override_match_and_makerspace_pk_alias_is_supported(scope_setup):
    actor, home, away = scope_setup
    original = Response({"code": "permission_denied"}, status=403)
    assert outsider_refusal(original, _context(actor, away.pk, kwargs={"makerspace_id": home.pk})) is original
    result = outsider_refusal(original, _context(actor, "bad", kwargs={"makerspace_pk": away.pk}))
    assert (result.status_code, result.data["code"]) == (404, "not_found")


@pytest.mark.parametrize("claims", [{"kind": "platform"}, {"surface": "platform"},
                                    {"makerspace": 1}, {"kind": None}, {"surface": None}])
def test_signed_token_cannot_change_account_context(claims):
    actor = person("cx6-token-context")
    token = SpaceWorksRefreshToken.for_user(actor).access_token
    for key, value in claims.items():
        token[key] = value
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert response.data["code"] == "authentication_failed"


def test_a_person_token_still_reaches_the_shared_account_utility():
    actor = person("cx6-token-valid")
    token = SpaceWorksRefreshToken.for_user(actor).access_token
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 200
    assert response.data["id"] == actor.pk
