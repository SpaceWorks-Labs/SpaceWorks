"""Decisions 481/494/520: personal standing must precede switch disclosure.

These regressions intentionally keep the required 404 contract. The current
personal_space and row-action ordering need the notifications owner's review.
"""
from datetime import timedelta
from uuid import uuid4

import pytest
from django.utils import timezone

from apps.notifications.models_inbox import NotificationInboxRow
from tests.inventory.switch_support_cx11b_p1 import snapshot
from tests.modules.switch_matrix_helpers import MODULE_KEYS, live_space
from tests.modules.switch_matrix_object_helpers import response_pair, retained
from tests.modules.test_switch_matrix_objects_rest_support import no_domain_writes, switch
from tests.notifications.test_object_switches_cx11b_p2 import personal_client
from tests.payments.account_helpers import make_payer

pytestmark = [pytest.mark.django_db, pytest.mark.area_notifications]


def addressed(space, person, title):
    return NotificationInboxRow.objects.create(makerspace=space, user=person,
        feature="hardware_requests", event="issued", event_key=uuid4(), audience="member", title=title)


def stage(space, key, state):
    if state != "on":
        original = switch(space, key)
        if state == "restored":
            switch(space, key, original=original)


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("operation,key", [
    ("inbox", "notifications"), ("inbox", "notifications.member_inbox"),
    ("preferences", "notifications"), ("preferences", "notifications.member_preferences"),
    ("snooze", "notifications"), ("snooze", "notifications.inbox_snooze"),
])
@pytest.mark.parametrize("state", ["on", "off", "restored"])
def test_foreign_personal_caller_without_standing_is_hidden_before_and_after_switch(native, operation, key, state):
    space = live_space("fix-personal-target", MODULE_KEYS)
    other = live_space("fix-personal-foreign", MODULE_KEYS)
    owner = make_payer("fix-personal-owner", space)
    stranger = make_payer("fix-personal-stranger", other)
    row = addressed(space, owner, "Private target")
    own = addressed(other, stranger, "Own admitted notice")
    client = personal_client(stranger, other, native)
    # Establish an admitted personal transport, independently of the target tenant.
    admitted = client.get(f"/api/v1/notifications/inbox/{other.pk}")
    assert response_pair(admitted) == (200, None), getattr(admitted, "data", None)
    assert [item["id"] for item in admitted.data["results"]] == [own.pk]
    stage(space, key, state)
    objects = {"private": row, "own": own}
    before, rows = retained(objects), snapshot(objects)
    url = f"/api/v1/notifications/{'preferences' if operation == 'preferences' else 'inbox'}/{space.pk}"
    with no_domain_writes():
        if operation == "snooze":
            response = client.post(url + f"/{row.pk}/snooze",
                {"until": (timezone.now() + timedelta(hours=2)).isoformat()}, format="json")
        else:
            response = client.get(url)
    # 494 preserves the fixed native selection refusal; browser lookup conceals standing.
    expected = (403, "permission_denied") if native else (404, "not_found")
    assert response_pair(response) == expected, getattr(response, "data", None)
    assert retained(objects) == before
    assert snapshot(objects) == rows


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("key", ["notifications", "notifications.member_inbox", "notifications.inbox_snooze"])
@pytest.mark.parametrize("state", ["on", "off", "restored"])
def test_same_space_nonowner_snooze_hides_addressed_row_before_gate(native, key, state):
    space = live_space("fix-personal-nonowner", MODULE_KEYS)
    owner = make_payer("fix-notice-owner", space)
    peer = make_payer("fix-notice-peer", space)
    row = addressed(space, owner, "Owner's private notice")
    own = addressed(space, peer, "Peer's own notice")
    client = personal_client(peer, space, native)
    admitted = client.get(f"/api/v1/notifications/inbox/{space.pk}")
    assert response_pair(admitted) == (200, None), getattr(admitted, "data", None)
    assert [item["id"] for item in admitted.data["results"]] == [own.pk]
    stage(space, key, state)
    objects = {"private": row, "own": own}
    before, rows = retained(objects), snapshot(objects)
    with no_domain_writes():
        response = client.post(f"/api/v1/notifications/inbox/{space.pk}/{row.pk}/snooze",
            {"until": (timezone.now() + timedelta(hours=2)).isoformat()}, format="json")
    assert response_pair(response) == (404, "not_found"), getattr(response, "data", None)
    assert retained(objects) == before
    assert snapshot(objects) == rows
