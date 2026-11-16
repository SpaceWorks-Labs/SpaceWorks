"""Security level: standing in a makerspace is decided before its module gate (decision 481(1)).

An actor with no standing in a space gets the answer a missing space gets, byte for byte, even when
the module is off there; an actor who belongs to the space still learns `module_disabled` and still
gets the 403 for an action they lack; the platform superadmin is unchanged.
"""
import pytest
from rest_framework.test import APIClient

from apps.makerspaces.capabilities import FEATURES
from apps.makerspaces.module_registry import MODULE_KEYS
from tests.accounts.reauth_helpers import force_recent_authenticate
from tests.audit_explorer_helpers import superadmin
from tests.fixed_roles.helpers import staff_account
from tests.member_submission import active_member_client
from tests.return_helpers import make_space

pytestmark = pytest.mark.django_db

URL = "/api/v1/admin/makerspace/{}/inventory"
GONE = 987654321
MISSING = {"detail": "Not found.", "code": "not_found"}


def _client(user):
    client = APIClient()
    force_recent_authenticate(client, user=user)
    return client


def _space(slug, *, inventory=True):
    space = make_space(slug)
    space.enabled_modules = sorted(k for k in MODULE_KEYS if inventory or k != "public_inventory")
    space.enabled_features = sorted(FEATURES)
    space.save(update_fields=["enabled_modules", "enabled_features"])
    return space


def test_an_outsider_gets_the_missing_space_answer_even_where_the_module_is_off():
    home, off = _space("lvl-standing-home"), _space("lvl-standing-off", inventory=False)
    on = _space("lvl-standing-on")
    client = _client(staff_account(home, "lvl-standing-outsider", "space_manager"))
    answers = [client.get(URL.format(space_id)) for space_id in (off.pk, on.pk, GONE)]
    assert [r.status_code for r in answers] == [404, 404, 404]
    assert [r.json() for r in answers] == [MISSING, MISSING, MISSING]
    write = client.post(URL.format(on.pk), {}, format="json")
    assert (write.status_code, write.json()) == (404, MISSING)


def test_a_manager_of_the_space_still_learns_the_module_is_off():
    space = _space("lvl-standing-mine", inventory=False)
    response = _client(staff_account(space, "lvl-standing-manager", "space_manager")).get(URL.format(space.pk))
    assert response.status_code == 404
    assert response.json()["code"] == "module_disabled"


def test_a_member_without_the_action_still_gets_the_403():
    space = _space("lvl-standing-members")
    _member, client = active_member_client(space, "lvl-standing-member")
    response = client.get(URL.format(space.pk))
    assert response.status_code == 403
    assert response.json()["code"] == "permission_denied"


def test_the_superadmin_is_unchanged():
    off = _space("lvl-standing-root-off", inventory=False)
    client = _client(superadmin("lvl-standing-root"))
    module_off = client.get(URL.format(off.pk))
    assert (module_off.status_code, module_off.json()["code"]) == (404, "module_disabled")
    assert client.get(URL.format(GONE)).status_code == 404
