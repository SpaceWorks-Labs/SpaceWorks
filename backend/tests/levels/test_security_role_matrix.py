"""Security level: privilege escalation, generated from the RBAC action matrix instead of listed by hand.

For every built-in role and every action in the vocabulary, `rbac.can` answers exactly what the role catalogue
grants (plus what the grant implies) in the person's own makerspace, and never in another one. A role cannot
quietly gain an action, and a new action defaults to "nobody but a Space Manager" until a role lists it.
"""
import pytest
from rest_framework.test import APIClient

from apps.accounts import rbac
from apps.accounts.models import User
from apps.accounts.rbac_actions import Action, expand_implied_actions
from apps.makerspaces.role_catalog import ROLE_CATALOG
from tests.accounts.reauth_helpers import force_recent_authenticate
from tests.fixed_roles.helpers import staff_account
from tests.return_helpers import make_space

pytestmark = pytest.mark.django_db

ACTIONS = sorted({v for k, v in vars(Action).items() if k.isupper() and isinstance(v, str)})
ROLES = [r for r in ROLE_CATALOG]


@pytest.fixture
def spaces():
    return make_space("lvl-matrix-home"), make_space("lvl-matrix-away")


def test_the_action_vocabulary_is_not_empty():
    assert len(ACTIONS) > 30


@pytest.mark.parametrize("role", ROLES, ids=[r.slug for r in ROLES])
def test_a_role_holds_exactly_its_catalogue_actions_at_home_and_nothing_abroad(role, spaces):
    home, away = spaces
    user = staff_account(home, f"lvl-{role.slug}", role.slug)
    expected = expand_implied_actions(role.granted_actions)
    wrong_home = [a for a in ACTIONS if rbac.can(user, a, home.pk) != (a in expected)]
    leaked_abroad = [a for a in ACTIONS if rbac.can(user, a, away.pk)]
    assert wrong_home == [], f"{role.slug} differs from the catalogue at home"
    assert leaked_abroad == [], f"{role.slug} holds actions in another makerspace"


@pytest.mark.parametrize("role", ROLES, ids=[r.slug for r in ROLES])
def test_no_role_but_a_space_manager_holds_a_settings_or_staff_action(role, spaces):
    if role.slug == "space_manager":
        pytest.skip("the Space Manager is the one role that holds them")
    home, _away = spaces
    user = staff_account(home, f"lvl-esc-{role.slug}", role.slug)
    forbidden = {Action.MANAGE_MAKERSPACE, Action.MANAGE_MEMBERS}
    assert {a for a in forbidden if rbac.can(user, a, home.pk)} == set()


def test_no_actions_without_a_membership(spaces):
    home, _ = spaces
    outsider = User.objects.create_user(username="lvl-outsider", email="lvl-outsider@example.test",
                                        access_status=User.AccessStatus.ACTIVE)
    assert [a for a in ACTIONS if rbac.can(outsider, a, home.pk)] == []
    assert [a for a in ACTIONS if rbac.can(outsider, a, None)] == []


@pytest.mark.parametrize("status", [User.AccessStatus.RESTRICTED, User.AccessStatus.SUSPENDED])
def test_a_restricted_or_suspended_manager_is_refused_on_staff_routes(status, spaces):
    home, _ = spaces
    manager = staff_account(home, f"lvl-{status}", "space_manager")
    client = APIClient(raise_request_exception=False)
    force_recent_authenticate(client, user=manager)
    url = f"/api/v1/admin/makerspace/{home.pk}/inventory"
    assert client.get(url).status_code == 200  # control: the same person is let in while active
    User.objects.filter(pk=manager.pk).update(access_status=status)
    manager.refresh_from_db()
    client = APIClient(raise_request_exception=False)
    force_recent_authenticate(client, user=manager)
    assert client.get(url).status_code in (401, 403)
