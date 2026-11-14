"""Add-on-linked lists must be removed before event/add-on parents (CX12)."""
from uuid import uuid4

import pytest
from django.apps import apps
from django.db import models, transaction
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.events import checkin_lists
from apps.events.models import EventAddon, EventCheckInList, EventCheckInListScan, EventRegistration
from apps.makerspaces.lifecycle_purge import purge
from apps.makerspaces.models import Makerspace
from tests.events.orders_helpers import l6_space, make_staff, verified
from tests.events.ticketing_helpers import open_event
from tests.return_helpers import authenticated_client

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.area_events]


def _world(slug):
    space = l6_space(slug)
    space.enabled_features = sorted(set(space.enabled_features) | {"events.checkin_lists"})
    space.save(update_fields=["enabled_features"])
    actor = make_staff(space)
    event = open_event(space)
    addon = EventAddon.objects.create(makerspace=space, event=event, name="Lunch", kind="meal")
    checkin_list = checkin_lists.create(event, actor=actor, data={"name": "Lunch", "addon_id": addon.pk})
    attendee = verified(slug + "-attendee")
    registration = EventRegistration.objects.create(event=event, member=attendee, name=attendee.username,
        email=attendee.email, phone="12345678", status="registered")
    # A general tally supplies real immutable scan history without inventing a purchase.
    tally = checkin_lists.create(event, actor=actor, data={"name": "Swag"})
    scan, result = checkin_lists.scan(event, actor=actor, list_id=tally.pk,
        registration_id=registration.pk, operation_id=uuid4())
    assert result == (1, 1, None)
    return space, event, addon, checkin_list, scan, registration, tally


def _direct_tenant_rows(space_id):
    result = {}
    for model in apps.get_models():
        fields = [field for field in model._meta.concrete_fields
                  if field.name == "makerspace" and field.is_relation and field.remote_field.model is Makerspace]
        if fields:
            result[model._meta.label] = list(model._base_manager.filter(makerspace_id=space_id).order_by("pk").values())
    return result


def _cycle_capabilities_then_disable(world):
    space, event = world[:2]
    client = authenticated_client(world[3].created_by)
    enabled = list(space.enabled_features)
    retained_models = (EventAddon, EventCheckInList, EventCheckInListScan, EventRegistration)

    def retained():
        return {model._meta.label: list(model._base_manager.order_by("pk").values()) for model in retained_models}

    before = retained()
    surfaces = (
        ("events.checkin_lists", reverse("events-programme-admin-checkin-lists", args=[event.pk]),
         {"code": "not_found", "detail": "Not found.", "fields": {}}),
        ("events.addons", reverse("admin-event-addons", args=[event.pk]),
         {"code": "feature_disabled", "detail": "This events feature is turned off.", "feature": "events.addons"}),
    )
    for feature, url, error in surfaces:
        live = client.get(url)
        assert live.status_code == 200
        if feature == "events.checkin_lists":
            assert {row["id"] for row in live.json()} == {world[3].pk, world[6].pk}
            tally = next(row for row in live.json() if row["id"] == world[6].pk)
            assert (tally["collected"], tally["collected_people"]) == (1, 1)
        else:
            assert [row["id"] for row in live.json()["results"]] == [world[2].pk]
        space.enabled_features = [key for key in enabled if key != feature]
        space.save(update_fields=["enabled_features"])
        refused = client.get(url)
        assert refused.status_code == 404
        assert refused.json() == error
        assert retained() == before
        space.enabled_features = enabled
        space.save(update_fields=["enabled_features"])
        restored = client.get(url)
        assert restored.status_code == 200
        assert restored.json() == live.json()
        assert retained() == before
    # Both switches are off when the authorized collector runs below.
    space.enabled_features = [key for key in enabled if key not in {"events.checkin_lists", "events.addons"}]
    space.save(update_fields=["enabled_features"])
    space.refresh_from_db()
    assert set(space.enabled_features).isdisjoint({"events.checkin_lists", "events.addons"})
    assert retained() == before


@pytest.mark.parametrize("managed", [False, True])
@pytest.mark.parametrize("events_enabled", [False, True])
def test_tenant_purge_removes_addon_lists_scans_and_only_the_selected_tenant(settings, managed, events_enabled):
    settings.MANAGED_POSTGRES = managed
    doomed = _world("list-purge-doomed")
    kept = _world("list-purge-kept")
    space_id, kept_id = doomed[0].pk, kept[0].pk
    _cycle_capabilities_then_disable(doomed)
    if not events_enabled:
        doomed[0].enabled_modules = [key for key in doomed[0].enabled_modules if key != "events"]
        doomed[0].save(update_fields=["enabled_modules"])
    root = User.objects.create_superuser("list-purge-root", "root@example.test", "pw-strong-123")
    Makerspace.objects.filter(pk=space_id).update(archived_at=timezone.now())
    doomed[0].refresh_from_db()
    kept_before = _direct_tenant_rows(kept_id)
    purge(doomed[0], root)
    assert not Makerspace.objects.filter(pk=space_id).exists()
    assert Makerspace.objects.filter(pk=kept_id).exists()
    assert all(rows == [] for rows in _direct_tenant_rows(space_id).values())
    assert _direct_tenant_rows(kept_id) == kept_before
    for row in doomed[1:]:
        assert type(row)._base_manager.filter(pk=row.pk).count() == 0


def test_events_module_purge_uses_the_same_child_order_and_preserves_the_other_tenant():
    from apps.makerspaces.module_purge import purge_module

    doomed, kept = _world("list-module-doomed"), _world("list-module-kept")
    _cycle_capabilities_then_disable(doomed)
    root = User.objects.create_superuser("list-module-root", "module-root@example.test", "pw-strong-123")
    doomed[0].enabled_modules = [key for key in doomed[0].enabled_modules if key != "events"]
    doomed[0].save(update_fields=["enabled_modules"])
    kept_before = _direct_tenant_rows(kept[0].pk)
    purge_module(doomed[0], "events", root)
    assert Makerspace.objects.filter(pk=doomed[0].pk).exists()
    for row in doomed[1:]:
        assert type(row)._base_manager.filter(pk=row.pk).count() == 0
    assert _direct_tenant_rows(kept[0].pk) == kept_before


def test_checkin_list_purge_order_export_classification_and_protect_contract():
    from apps.data_export.classification import EXPORTED_MODEL_FIELDS
    from apps.data_export.classification_r2_l21a import DATASET_SPECS
    from apps.makerspaces.purge_events_programme_catalog import PURGE_ORDER

    order = [label for label, _owner in PURGE_ORDER]
    assert order.index("events.EventCheckInListScan") < order.index("events.EventCheckInList")
    for model, dataset in ((EventCheckInList, "events/checkin_lists.csv"),
                           (EventCheckInListScan, "events/checkin_list_scans.csv")):
        label = model._meta.label
        assert PURGE_ORDER.count((label, "makerspace")) == 1
        assert set(EXPORTED_MODEL_FIELDS[label].split()) == {field.name for field in model._meta.concrete_fields}
        path, predicate = DATASET_SPECS[label]
        assert path == dataset
        assert predicate.any_paths == ("makerspace",)
    assert EventCheckInList._meta.get_field("addon").remote_field.on_delete is models.PROTECT


def test_programme_purge_still_requires_the_enclosing_transaction():
    from apps.makerspaces.purge_events_programme import delete_programme_rows

    assert not transaction.get_connection().in_atomic_block
    with pytest.raises(RuntimeError, match="Programme purge requires the enclosing authorized purge transaction."):
        delete_programme_rows(Makerspace())
