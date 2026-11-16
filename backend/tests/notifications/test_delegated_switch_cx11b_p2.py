"""Recipient delegation is an authority policy, with its existing exact 403 refusal."""
import pytest

from apps.integrations.models_recipients import NotificationRecipient
from tests.machines.test_phase6c2_delegated_recipients import make_actor, make_type, scoped_rule, url
from tests.modules.switch_matrix_helpers import MODULE_KEYS, live_space
from tests.modules.switch_matrix_object_helpers import client_for, response_pair
from tests.payments.switch_helpers_cx11b_p2 import route_cycle

pytestmark = [pytest.mark.django_db, pytest.mark.area_notifications, pytest.mark.area_machines]


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("key", ["notifications.delegated_recipients", "machines", "notifications", "machines.maintenance"])
def test_delegation_policy_restores_same_scoped_rule_after_switch(native, key):
    space = live_space("p2-delegate", MODULE_KEYS)
    machine_type = make_type(space, "p2-delegate-laser")
    actor, role = make_actor(space, machine_type, username="p2-delegate-actor")
    client = client_for(actor, space, native)
    body = {"feature": "maintenance", "event": "logged",
            "rules": [scoped_rule("role", machine_type, role_id=role.pk)]}
    saved = client.put(url(space), body, format="json")
    assert response_pair(saved) == (200, None), saved.data
    row = NotificationRecipient.objects.get(makerspace=space, role=role)
    route_cycle(space, client, {"rule": row, "machine_type": machine_type}, key, url(space),
        off=(403, "permission_denied"), check=lambda response: assert_delegated(response, machine_type))


def assert_delegated(response, machine_type):
    assert response.data["delegated"] is True
    assert response.data["scope_options"]["machine_types"] == [{"id": machine_type.pk, "name": machine_type.name}]
