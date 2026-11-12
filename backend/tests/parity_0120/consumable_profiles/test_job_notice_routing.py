"""Machine-service job notices: which staff get them is routable per machine type (decision 343)."""
import pytest
from django.urls import reverse

from apps.integrations.destinations import NotificationScope
from apps.integrations.models_recipients import NotificationRecipient, RecipientMachineTypeScope
from apps.integrations.recipients import requester_selected
from apps.integrations.recipients_staff_only import STAFF_EVENTS
from apps.integrations.staff_notifications import staff_user_ids_for_feature
from apps.machines.models import MachineType

from .helpers import client, manager, world

pytestmark = pytest.mark.django_db


def two_types(slug):
    w = world(slug)
    w.mill = MachineType.objects.create(makerspace=w.space, slug=f"{w.space.slug}-mill", name="Mill")
    return w


def ids(w, machine_type, event="completed"):
    return staff_user_ids_for_feature(w.space, "printing", event, NotificationScope(machine_type=machine_type))


def route(w, user, machine_type, event="completed"):
    rule = NotificationRecipient.objects.create(makerspace=w.space, feature="printing", event=event, kind="user",
                                                user=user)
    RecipientMachineTypeScope.objects.create(recipient=rule, machine_type=machine_type)
    return rule


def test_with_no_rules_the_audience_is_exactly_as_before():
    w = two_types("route-default")
    before = ids(w, w.kind)
    assert w.staff.pk in before and before == ids(w, w.mill)


def test_a_rule_narrowed_to_one_type_routes_only_that_types_notices():
    w = two_types("route-type")
    default = ids(w, w.mill)
    laser_lead = manager(w, w.kind)
    route(w, laser_lead, w.kind)
    assert ids(w, w.kind) == [laser_lead.pk]
    assert ids(w, w.mill) == default  # another type's notices keep the default audience
    assert ids(w, w.kind, "submitted") == ids(w, w.mill, "submitted")  # other events untouched


def test_a_staff_rule_never_silences_the_members_own_notice():
    w = two_types("route-member")
    route(w, manager(w, w.kind), w.kind)
    assert requester_selected(w.space, "printing", "completed", NotificationScope(machine_type=w.kind)) is True


def test_the_rules_endpoint_offers_staff_events_and_refuses_member_kinds():
    w = two_types("route-api")
    url = reverse("admin-notification-recipient-rules", kwargs={"makerspace_id": w.space.pk})
    features = {row["key"]: row["events"] for row in client(w.staff).get(url).data["features"]}
    assert tuple(features["printing"]) == STAFF_EVENTS["printing"] and "pickup_reminder" not in features["printing"]
    scope = {"machine_type_ids": [w.kind.pk], "machine_ids": [], "category_ids": []}
    member_rule = {"feature": "printing", "event": "completed", "rules": [{"kind": "requester", "scope": scope}]}
    assert client(w.staff).put(url, member_rule, format="json").status_code == 400
    owner_only = {"feature": "printing", "event": "pickup_reminder", "rules": []}
    assert client(w.staff).put(url, owner_only, format="json").status_code == 400
    lead = manager(w, w.kind)
    good = {"feature": "printing", "event": "failed", "rules": [{"kind": "user", "user_id": lead.pk, "scope": scope}]}
    response = client(w.staff).put(url, good, format="json")
    assert response.status_code == 200, response.data
    assert ids(w, w.kind, "failed") == [lead.pk]
