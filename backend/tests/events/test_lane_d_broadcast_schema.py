"""Pin both broadcast contracts so one domain cannot replace the other's components."""

import pytest
from drf_spectacular.generators import SchemaGenerator


@pytest.mark.django_db
def test_event_and_notification_broadcast_schema_components_are_distinct():
    schema = SchemaGenerator().get_schema(request=None, public=True)
    components = schema["components"]["schemas"]
    paths = schema["paths"]
    event = paths["/api/v1/admin/events/{id}/broadcasts/"]
    notification = paths["/api/v1/notifications/broadcasts/{makerspace_id}"]["post"]

    def ref(name):
        return {"$ref": f"#/components/schemas/{name}"}

    for operation, name in ((event["post"], "EventBroadcastInput"), (notification, "BroadcastInput")):
        for media in operation["requestBody"]["content"].values():
            assert media["schema"] == ref(name)
    assert set(components["BroadcastInput"]["required"]) == {"title", "body"}
    assert set(components["BroadcastInput"]["properties"]) == {
        "title", "body", "plan_id", "status", "certification_id",
    }
    assert components["BroadcastInput"]["properties"]["body"]["maxLength"] == 12000
    assert set(components["Broadcast"]["properties"]) == {"id", "title", "body", "created_at"}
    assert notification["responses"]["201"]["content"]["application/json"]["schema"] == ref("BroadcastResult")
    assert components["BroadcastResult"]["properties"]["broadcast"] == ref("Broadcast")
    assert set(components["EventBroadcastInput"]["required"]) == {"subject", "body"}
    assert "event" in components["EventBroadcast"]["properties"]
    assert "subject" in components["EventBroadcast"]["properties"]
    assert "title" not in components["EventBroadcast"]["properties"]
    assert event["post"]["responses"]["201"]["content"]["application/json"]["schema"] == ref("EventBroadcast")
    assert event["get"]["responses"]["200"]["content"]["application/json"]["schema"] == ref("EventBroadcastList")
    assert components["EventBroadcastList"]["properties"]["results"]["items"] == ref("EventBroadcast")
    for action in ("queue", "cancel"):
        operation = paths[f"/api/v1/admin/events/{{id}}/broadcasts/{{campaign_id}}/{action}/"]["post"]
        assert operation["responses"]["200"]["content"]["application/json"]["schema"] == ref("EventBroadcast")
