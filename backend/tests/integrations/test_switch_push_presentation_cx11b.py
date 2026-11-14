"""CX11B: watch actions are a payload policy, with no invented object URL."""
import pytest
from django.db import connection

from apps.integrations.push_payload import push_data
from tests.modules.switch_matrix_helpers import MODULE_KEYS, live_space
from tests.modules.test_switch_matrix_objects_rest_support import _no_write, domain_rows, switch

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("key,off_category", [("mobile.watch_actions", None), ("notifications.inbox_snooze", "sw.inbox")])
def test_push_presentation_switches_remove_actions_without_changing_the_notification(key, off_category):
    space = live_space("cx11b-push-policy", MODULE_KEYS)
    values = {"event_id": "cx11b-event", "makerspace_id": space.pk, "feature": "bookings",
              "event": "confirmed", "inbox_row_id": 1, "makerspace": space}
    with connection.execute_wrapper(_no_write):
        on = push_data(**values)
    assert on["category"] == "sw.inbox.snooze"
    before = domain_rows()
    original = switch(space, key)
    with connection.execute_wrapper(_no_write):
        off = push_data(**values)
    assert off.get("category") == off_category
    assert {k: v for k, v in off.items() if k != "category"} == {k: v for k, v in on.items() if k != "category"}
    assert domain_rows() == before
    switch(space, key, original=original)
    with connection.execute_wrapper(_no_write):
        assert push_data(**values) == on
    assert domain_rows() == before
