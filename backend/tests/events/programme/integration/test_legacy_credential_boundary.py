from uuid import uuid4

from apps.events.serializers_checkin import EventCheckInResolveRequestSerializer


def test_legacy_qr_is_validated_before_uuid_database_lookup():
    for value in ("bad-uuid", "SWEC2." + "a" * 43):
        serializer = EventCheckInResolveRequestSerializer(data={"checkin_token": value})
        assert not serializer.is_valid()
        assert "checkin_token" in serializer.errors


def test_checkin_request_keeps_legacy_and_v2_namespaces_exclusive():
    token = uuid4()
    serializer = EventCheckInResolveRequestSerializer(data={"checkin_token": str(token)})
    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data["checkin_token"] == token
    for data in ({}, {"checkin_token": str(token), "credential": "SWEC2." + "a" * 43}):
        assert not EventCheckInResolveRequestSerializer(data=data).is_valid()
