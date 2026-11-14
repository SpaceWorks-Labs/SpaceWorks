"""Decision 520: an object outsider cannot observe its disabled switch."""
from types import SimpleNamespace

import pytest
from django.db import connection
from django.urls import reverse
from django.utils import timezone
from rest_framework.exceptions import NotFound

from apps.accounts.models import User
from apps.machines.models import SupervisedSession
from apps.maintenance.incidents.models import Incident
from tests.accounts.account_factories import make_staff
from tests.modules.switch_matrix_helpers import MODULE_KEYS, live_space
from tests.modules.switch_matrix_object_helpers import client_for, object_world, response_pair
from tests.modules.test_switch_matrix_objects_rest_support import _no_write, no_domain_writes, switch

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.area_machines, pytest.mark.area_inventory]


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("kind", ["supervised", "incident"])
def test_object_standing_precedes_the_switch_for_foreign_staff(kind, native):
    space, own, objects = object_world(native)
    actor = User.objects.get(username="sx-real-object-manager")
    foreign_space = live_space("p1-standing-foreign", MODULE_KEYS)
    outsider = make_staff(foreign_space, username="p1-standing-outsider", access_status="active")
    client = client_for(outsider, foreign_space, native)
    if kind == "supervised":
        row = SupervisedSession.objects.create(makerspace=space, machine=objects["machine"], instructor=actor,
                                                opened_at=timezone.now())
        key, name = "machines.supervised_sessions", "member-supervised-session"
    else:
        row = Incident.objects.create(makerspace=space, title="Retained report", reporter=actor, area="other")
        key, name = "safety.incidents", "admin-incident-detail"
    url = reverse(name, kwargs={"pk": row.pk})
    expected = (403, "permission_denied") if native else (404, "not_found")
    with no_domain_writes():
        assert response_pair(client.get(url)) == expected
    original = switch(space, key)
    with no_domain_writes():
        assert response_pair(client.get(url)) == expected
        response = own.get(url)
    assert response_pair(response) == (404, "feature_disabled")
    assert response.data["feature"] == key
    switch(space, key, original=original)
    assert response_pair(own.get(url)) == (200, None)
    assert type(row).objects.filter(pk=row.pk).exists()


@pytest.mark.parametrize("kind", ["supervised", "incident"])
def test_lookup_itself_checks_standing_before_disabled_feature(kind):
    space, _, objects = object_world(False)
    actor = User.objects.get(username="sx-real-object-manager")
    other = live_space("p1-lookup-foreign", MODULE_KEYS)
    outsider = make_staff(other, username="p1-lookup-outsider", access_status="active")
    if kind == "supervised":
        from apps.machines.views_supervised import _session
        row = SupervisedSession.objects.create(makerspace=space, machine=objects["machine"], instructor=actor,
                                                opened_at=timezone.now())
        key = "machines.supervised_sessions"
        lookup = lambda user: _session(SimpleNamespace(user=user), row.pk)
    else:
        from apps.maintenance.incidents.views import _staff_incident
        row = Incident.objects.create(makerspace=space, title="Retained report", reporter=actor, area="other")
        key = "safety.incidents"
        lookup = lambda user: _staff_incident(user, row.pk, read_only=True)
    switch(space, key)
    # Exercise the owning lookup as well as HTTP: origin admission must not mask
    # a regression in the helper used by all object actions.
    with connection.execute_wrapper(_no_write), pytest.raises(NotFound) as error:
        lookup(outsider)
    assert (error.value.status_code, error.value.get_codes()) == (404, "not_found")
    with connection.execute_wrapper(_no_write), pytest.raises(NotFound) as error:
        lookup(actor)
    assert error.value.status_code == 404
    assert error.value.detail["code"] == "feature_disabled"
    assert error.value.detail["feature"] == key
