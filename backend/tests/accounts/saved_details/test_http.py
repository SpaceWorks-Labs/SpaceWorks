import json
from pathlib import Path
from uuid import uuid4

import pytest
from django.urls import include, path
from drf_spectacular.generators import SchemaGenerator
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.accounts.models import User
from apps.accounts.saved_details import urls, views
from apps.accounts.saved_details.models import MemberSavedAsset

pytestmark = pytest.mark.django_db(transaction=True)


def dispatch(owner, view, request, **kwargs):
    force_authenticate(request, user=owner)
    return view.as_view()(request, **kwargs)


def test_list_and_writes_are_private_no_store_and_require_matching_header(owner):
    factory = APIRequestFactory()
    body = {"operation_id": str(uuid4()), "expected_version": 0, "value": "Maker College", "save_consent": True}
    refused = dispatch(owner, views.DetailView, factory.put("/", body, format="json"), field_key="institution")
    assert refused.status_code == 400
    accepted = dispatch(owner, views.DetailView, factory.put("/", body, format="json", HTTP_IDEMPOTENCY_KEY=body["operation_id"]), field_key="institution")
    assert accepted.status_code == 200 and accepted.data["version"] == 1
    response = dispatch(owner, views.DetailsView, factory.get("/"))
    assert response["Cache-Control"] == "private, no-store"
    assert response.data["fields"][0]["value"] == "Maker College"
    other = User.objects.create_user(username=f"other-{uuid4().hex}")
    assert dispatch(other, views.DetailsView, factory.get("/")).data["fields"] == []


def test_foreign_asset_is_uniform_404_and_unknown_inputs_reject(owner):
    other = User.objects.create_user(username=f"asset-{uuid4().hex}")
    asset = MemberSavedAsset.objects.create(user=other, object_key="foreign-final", staging_key="foreign-stage", verification_key="foreign-verify", size_bytes=10)
    factory = APIRequestFactory()
    foreign = dispatch(owner, views.ResumeDetailView, factory.get("/"), asset_id=asset.pk)
    unknown = dispatch(owner, views.ResumeDetailView, factory.get("/"), asset_id=asset.pk + 1000)
    assert foreign.status_code == unknown.status_code == 404
    assert foreign.data == unknown.data
    body = {"operation_id": str(uuid4()), "expected_version": 0, "value": "College", "save_consent": True, "user_id": other.pk}
    refused = dispatch(owner, views.DetailView, factory.put("/", body, format="json", HTTP_IDEMPOTENCY_KEY=body["operation_id"]), field_key="institution")
    assert refused.status_code == 400


def test_every_frozen_p_route_has_named_provider_and_documented_methods():
    fixture = json.loads((Path(__file__).parents[2] / "events/programme/contracts/fixtures/routes-v3.json").read_text())
    expected = {route["name"]: route for route in fixture["routes"] if route["owner"] == "P"}
    assert set(expected) == {route.name for route in urls.urlpatterns}
    schema = SchemaGenerator(patterns=[path("api/v1/member/saved-details/", include(urls))]).get_schema(request=None, public=True)
    for route in expected.values():
        documented = schema["paths"][route["path"]]
        for method in route["operations"]:
            if method == "HEAD":
                continue  # DRF automatically serves the matching authorized GET headers
            operation = documented[method.lower()]
            assert operation.get("security")
            assert "503" in operation["responses"] and "403" in operation["responses"]
