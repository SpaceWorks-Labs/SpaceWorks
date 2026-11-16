"""Exact retained folded-capability objects and command effects."""
from tests.bookings.route_support_cx11b_g1 import fields


def folded_result(op, body, objects, response):
    row, name, method = objects[op.target], op.name, op.method
    if op.target == "schedule":
        if method == "PATCH":
            fields(row, description=body["description"], is_active=True)
            return ["maintenance.schedule_updated"]
        fields(row, is_active=False)
        return ["maintenance.schedule_deactivated"]
    if name == "admin-machine-warranty":
        warranty = objects["warranty"]
        warranty.refresh_from_db()
        assert response.data["id"] == warranty.pk
        assert warranty.vendor_name == (body["vendor_name"] if method == "PUT" else "Retained warranty supplier")
        return ["warranty.updated"] if method == "PUT" else []
    if op.target == "vendor":
        fields(row, name=body["name"])
        assert response.data["id"] == row.pk
        return ["vendor.updated"]
    if op.target in {"tobuy", "machine_tobuy"}:
        if method == "DELETE":
            assert not type(row).objects.filter(pk=row.pk).exists()
            return ["procurement.item_removed"]
        row.refresh_from_db()
        assert (response.data["id"], response.data["name"], row.quantity) == (
            row.pk, body["name"] if method == "PATCH" else "Retained procurement item", 2)
        if method == "PATCH":
            assert row.name == body["name"]
        return ["procurement.item_updated"] if method == "PATCH" else []
    if op.target == "incident_action":
        row.refresh_from_db()
        assert row.done_at is not None and row.done_by_id is not None
        return ["incident.action_done"]
    if name == "admin-incident-actions":
        from apps.maintenance.incidents.models import IncidentAction
        assert list(IncidentAction.objects.filter(incident=row).order_by("pk").values_list("description", flat=True)) == [
            "Retained follow-up", "Check the guard"]
        return ["incident.action_added"]
    if method == "PATCH":
        fields(row, title=body["title"])
        return ["incident.updated"]
    assert (response.data["id"], response.data["title"]) == (row.pk, "Retained safety report")
    return []
