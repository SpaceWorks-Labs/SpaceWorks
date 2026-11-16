"""HTTP error envelopes and cache policy are enforced by the lane boundary."""
from django.http import Http404
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIRequestFactory
from apps.events.hackathons.api_base import ProgrammeView


class MissingView(ProgrammeView):
    authentication_classes = []
    permission_classes = []
    def get(self, request):
        raise Http404


class InvalidView(MissingView):
    def get(self, request):
        raise ValidationError({"answers": {"emergency": {"phone": ["Required."]}}})


def test_foreign_or_missing_target_returns_stable_not_found_and_no_store():
    response = MissingView.as_view()(APIRequestFactory().get("/lane-a-test/"))
    assert response.status_code == 404 and response.data["code"] == "not_found"
    assert response["Cache-Control"] == "private, no-store"
    assert "Authorization" in response["Vary"]


def test_nested_emergency_error_paths_survive_boundary_normalization():
    response = InvalidView.as_view()(APIRequestFactory().get("/lane-a-test/"))
    assert response.status_code == 400 and response.data["code"] == "invalid_input"
    assert response.data["fields"]["answers"]["emergency"]["phone"] == ["Required."]
