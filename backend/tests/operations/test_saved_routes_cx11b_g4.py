"""Each saved report method proves its own persisted preference, not merely HTTP 200."""
import pytest
from django.urls import reverse

from apps.accounts.models import User
from apps.operations.models import SavedView
from tests.accounts.account_factories import make_staff
from tests.modules.switch_matrix_object_helpers import client_for, object_world
from tests.operations.route_support_cx11b_g4 import contains, cycle, outsider, send
from tests.operations.test_saved_report_views import payload

pytestmark = [pytest.mark.django_db, pytest.mark.area_reports]


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("key", ["reports", "reports.saved_views", "membership"])
@pytest.mark.parametrize("name,method", [("saved-report-views", "GET"), ("saved-report-views", "POST"),
    ("saved-report-view-detail", "GET"), ("saved-report-view-detail", "PATCH"), ("saved-report-view-detail", "DELETE")])
def test_saved_report_route_effect_and_retention(native, key, name, method):
    space, client, _ = object_world(native)
    actor = User.objects.get(username="sx-real-object-manager")
    row = SavedView.objects.create(makerspace=space, owner=actor, entity="report", **payload())
    foreign = outsider(native)
    kwargs = {"makerspace_id": space.pk}
    if name.endswith("detail"):
        kwargs["pk"] = row.pk
    url = reverse(name, kwargs=kwargs)
    body = payload(name="New report") if method == "POST" else {"name": "Changed report"} if method == "PATCH" else {}

    def check(response):
        if method == "DELETE":
            assert not SavedView.objects.filter(pk=row.pk).exists()
        elif method == "GET" and not name.endswith("detail"):
            contains(response, row.pk)
            assert response.data["results"][0]["state"] == payload()["state"]
        else:
            saved = SavedView.objects.get(pk=response.data["id"])
            expected = "New report" if method == "POST" else "Changed report" if method == "PATCH" else payload()["name"]
            assert (saved.name, saved.state, saved.owner_id, saved.entity) == (expected, payload()["state"], actor.pk, "report")
            assert response.data["state"] == saved.state
            assert SavedView.objects.filter(makerspace=space).count() == (2 if method == "POST" else 1)

    # Foreign space: decisions 481/494. A same-space non-owner also cannot read a private view (520).
    probes = []
    if name.endswith("detail"):
        peer = make_staff(space, username="g4-private-view-peer", access_status="active")
        peer_client = client_for(peer, space, native)
        probes.append((lambda: send(peer_client, method, url, body), (404, "not_found")))
    actions = {"POST": ("saved_view.created",), "PATCH": ("saved_view.updated",), "DELETE": ("saved_view.deleted",)}
    hidden_list = key == "membership" and method == "GET" and name == "saved-report-views"
    def empty(response):
        assert response.data["results"] == []
    cycle(space, key, lambda: send(client, method, url, body), check,
          on=(201 if method == "POST" else 204 if method == "DELETE" else 200, None),
          off=(200, None) if hidden_list else (404, "feature_disabled" if "." in key else "module_disabled"),
          off_check=empty if hidden_list else None,
          foreign=lambda: send(foreign, method, url, body), foreign_native=native, audit=actions.get(method, ()), extra_probes=probes)
