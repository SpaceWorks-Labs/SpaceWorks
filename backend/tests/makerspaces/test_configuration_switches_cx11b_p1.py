"""Space packs and closed notices keep their persisted configuration across switches."""
import pytest
from tests.modules.test_switch_matrix_objects_rest_isolation import cx11b_isolated_phase  # noqa: F401

from apps.makerspaces.platform import bootstrap_payload
from tests.inventory.switch_support_cx11b_p1 import prove_route, staff_outsiders
from tests.modules.switch_matrix_object_helpers import object_world, retained
from tests.modules.test_switch_matrix_objects_rest_support import switch

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.area_platform]


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
def test_pack_export_switch_keeps_the_same_seeded_configuration(native):
    space, client, objects = object_world(native)
    path = f"/api/v1/admin/makerspace/{space.pk}/space-pack"
    prove_route(space, client, objects, "packs.import", lambda c: c.get(path), outsiders=staff_outsiders(native))


def test_closed_notice_policy_hides_and_restores_saved_unicode_copy_without_writes():
    space, _, objects = object_world(False)
    space.public_closed_notice = "Closed — renovation"
    space.public_reopens_on = "2099-01-15"
    space.save(update_fields=["public_closed_notice", "public_reopens_on"])
    space.refresh_from_db()
    before = retained(objects)
    expected = {"text": "Closed — renovation", "reopens_on": "2099-01-15"}
    assert bootstrap_payload(space)["makerspace"]["closed_notice"] == expected
    original = switch(space, "public_site.closed_notice")
    from django.db import connection
    from tests.modules.test_switch_matrix_objects_rest_support import _no_write
    with connection.execute_wrapper(_no_write):
        assert "closed_notice" not in bootstrap_payload(space)["makerspace"]
    switch(space, "public_site.closed_notice", original=original)
    assert bootstrap_payload(space)["makerspace"]["closed_notice"] == expected
    assert retained(objects) == before

pytestmark = ([pytestmark] if not isinstance(pytestmark, list) else pytestmark) + [
    pytest.mark.usefixtures("cx11b_isolated_phase")]
