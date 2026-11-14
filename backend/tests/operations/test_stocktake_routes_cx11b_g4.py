"""Seeded stocktake route effects; standing precedes disclosure (481/494/520)."""
import pytest
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.operations.models import StocktakePolicy, StocktakeSchedule, StocktakeSession
from tests.modules.switch_matrix_object_helpers import object_world
from tests.operations.route_support_cx11b_g4 import contains, cycle, outsider, send

pytestmark = [pytest.mark.django_db, pytest.mark.area_inventory, pytest.mark.area_stocktake]

DISCIPLINE = [("stocktake-policy", "GET"), ("stocktake-policy", "PUT"),
              ("stocktake-schedules", "GET"), ("stocktake-schedules", "POST"),
              ("stocktake-schedule-detail", "GET"), ("stocktake-schedule-detail", "PATCH"),
              ("stocktake-schedule-detail", "DELETE")]


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("key", ["stocktake", "stocktake.discipline", "loans.enabled"])
@pytest.mark.parametrize("name,method", DISCIPLINE)
def test_stocktake_discipline_route_effect_and_retention(native, key, name, method):
    space, client, _ = object_world(native)
    foreign = outsider(native)
    policy = StocktakePolicy.objects.create(makerspace=space, blind_default=True, variance_threshold=3)
    row = StocktakeSchedule.objects.create(makerspace=space, name="Retained shelf", interval_days=30,
                                          next_due=timezone.localdate(), blind=True)
    kwargs = {"makerspace_id": space.pk}
    if name.endswith("detail"):
        kwargs["pk"] = row.pk
    url = reverse(name, kwargs=kwargs)
    body, audit = {}, ()
    if method == "PUT":
        body = {"blind_default": False, "variance_threshold": 7}
        audit = ("stocktake.policy_updated",)
    if method == "POST":
        body = {"name": "New shelf", "interval_days": 14, "next_due": str(timezone.localdate()), "blind": False}
        audit = ("stocktake.schedule_created",)
    if method == "PATCH":
        body, audit = {"name": "Renamed shelf", "interval_days": 21}, ("stocktake.schedule_updated",)
    if method == "DELETE":
        audit = ("stocktake.schedule_deleted",)

    def check(response):
        if name == "stocktake-policy":
            policy.refresh_from_db()
            expected = (False, 7) if method == "PUT" else (True, 3)
            assert (policy.blind_default, policy.variance_threshold) == expected
            assert response.data == dict(zip(("blind_default", "variance_threshold"), expected))
        elif method == "DELETE":
            assert not StocktakeSchedule.objects.filter(pk=row.pk).exists()
        elif name == "stocktake-schedules" and method == "GET":
            contains(response, row.pk)
            assert response.data["results"][0]["name"] == "Retained shelf"
        else:
            stored = StocktakeSchedule.objects.get(pk=response.data["id"])
            expected = ("New shelf", 14) if method == "POST" else (("Renamed shelf", 21) if method == "PATCH" else ("Retained shelf", 30))
            assert (stored.name, stored.interval_days) == expected
            assert (response.data["name"], response.data["interval_days"]) == expected
            assert StocktakeSchedule.objects.filter(makerspace=space).count() == (2 if method == "POST" else 1)

    cycle(space, key, lambda: send(client, method, url, body), check,
          on=(201 if method == "POST" else 204 if method == "DELETE" else 200, None),
          off=(404, "feature_disabled" if key == "stocktake.discipline" else "module_disabled"), audit=audit,
          refusal_key="stocktake.discipline" if key == "stocktake.discipline" else "stocktake",
          foreign=lambda: send(foreign, method, url, body), foreign_native=native)


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("key", ["stocktake", "loans.enabled"])
@pytest.mark.parametrize("name,method", [("stocktakes", "GET"), ("stocktakes", "POST"),
    ("stocktake-detail", "GET"), ("stocktake-count-lines", "POST"), ("stocktake-complete", "POST")])
def test_stocktake_workflow_route_effect_and_retention(native, key, name, method):
    from apps.operations.models import StocktakeLine
    from tests.return_helpers import make_product
    space, client, objects = object_world(native)
    actor = User.objects.get(username="sx-real-object-manager")
    row = objects["stocktake"]
    # Complete requires COUNTING. Keep discipline's threshold absent so approval remains explicit.
    row.status, row.variance_threshold = "counting", None
    row.save(update_fields=["status", "variance_threshold"])
    product = make_product(space)
    if name == "stocktake-complete":
        StocktakeLine.objects.create(stocktake=row, product=product, expected_quantity=10,
                                    counted_quantity=8, variance_quantity=-2)
    kwargs = {"makerspace_id": space.pk} if name == "stocktakes" else {"pk": row.pk}
    url = reverse(name, kwargs=kwargs)
    body = {"notes": "New count", "blind": False} if name == "stocktakes" else {}
    if name == "stocktake-count-lines":
        body = {"product_id": product.pk, "counted_quantity": 8, "notes": "Two missing"}
    actions = {"stocktakes": "stocktake.created", "stocktake-count-lines": "stocktake.line_counted",
               "stocktake-complete": "stocktake.completed"}

    def check(response):
        if method == "GET":
            if name == "stocktakes":
                contains(response, row.pk)
            else:
                assert (response.data["id"], response.data["status"]) == (row.pk, "counting")
        elif name == "stocktakes":
            created = StocktakeSession.objects.get(pk=response.data["id"])
            assert (created.notes, created.started_by_id, created.blind) == ("New count", actor.pk, False)
            assert StocktakeSession.objects.filter(makerspace=space).count() == 2
        elif name == "stocktake-count-lines":
            line = StocktakeLine.objects.get(stocktake=row)
            assert (line.product_id, line.counted_quantity, line.expected_quantity, line.variance_quantity,
                    line.notes) == (product.pk, 8, 10, -2, "Two missing")
        else:
            row.refresh_from_db()
            assert (row.status, row.approval_required) == ("completed", True)
            assert row.completed_at is not None
    foreign = outsider(native)
    cycle(space, key, lambda: send(client, method, url, body), check, refusal_key="stocktake",
          on=(201 if method == "POST" and name != "stocktake-complete" else 200, None),
          audit=(actions[name],) if method == "POST" else (),
          foreign=lambda: send(foreign, method, url, body), foreign_native=native)
