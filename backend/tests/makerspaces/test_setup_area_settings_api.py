"""Configured installer values remain scoped, validated and audited in staff settings."""
import pytest
from django.urls import reverse
from drf_spectacular.generators import SchemaGenerator

from apps.audit.models import AuditLog
from tests.events.checkin_helpers import client_for, make_space

from tests.account_split.sweep_g1_helpers import event_staff as make_staff

pytestmark = pytest.mark.django_db


def test_request_access_is_read_only_and_the_removed_switch_is_ignored():
    space = make_space("access-editor")
    space.enabled_modules = [key for key in space.enabled_modules if key != "membership"]
    space.save(update_fields=["enabled_modules"])
    response = client_for(make_staff(space)).patch(reverse("admin-makerspace", kwargs={"pk": space.pk}),
                                                  {"anonymous_requests_enabled": True}, format="json")
    assert response.status_code == 200
    assert response.data["request_access"] == "accounts"
    assert "anonymous_requests_enabled" not in response.data
    assert not AuditLog.objects.filter(makerspace=space, action="makerspace.request_access_changed").exists()


def test_new_settings_are_scoped_and_validate_event_audience():
    own, other = make_space("own-default"), make_space("other-default")
    client = client_for(make_staff(own))
    response = client.patch(reverse("admin-makerspace", kwargs={"pk": other.pk}),
                            {"event_default_registration_audience": "accounts"}, format="json")
    assert response.status_code in (403, 404)
    response = client.patch(reverse("admin-makerspace", kwargs={"pk": own.pk}),
                            {"event_default_registration_audience": "everyone"}, format="json")
    assert response.status_code == 400
    response = client.patch(reverse("admin-makerspace", kwargs={"pk": own.pk}),
                            {"event_default_registration_audience": "accounts"}, format="json")
    assert response.status_code == 200
    assert AuditLog.objects.filter(makerspace=own, action="makerspace.updated").exists()


def test_new_settings_and_response_metadata_have_openapi_entries():
    schemas = SchemaGenerator().get_schema(request=None, public=True)["components"]["schemas"]
    assert "event_default_registration_audience" in schemas["Makerspace"]["properties"]
    assert "anonymous_requests_enabled" not in schemas["Makerspace"]["properties"]
    assert schemas["Makerspace"]["properties"]["request_access"]["readOnly"]
    assert schemas["TimingPolicy"]["properties"]["daily_digest_default"]["type"] == "boolean"
    assert "default_registration_audience" in schemas["EventListWithDefaults"]["properties"]
    assert "default_registration_audience" not in schemas["EventListResponse"]["properties"]
