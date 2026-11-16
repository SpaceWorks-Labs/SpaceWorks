import json
from pathlib import Path

import pytest
from django.urls import resolve
from rest_framework.exceptions import ValidationError

from apps.events.judging.serializers import ScoreInput, SponsorGrantInput, validated
from apps.events.judging.errors import ProgrammeError
from apps.events.judging.urls import urlpatterns
from apps.events.submissions.gallery_serializers import GalleryWithdrawInput

FIXTURES = Path(__file__).parents[1] / "contracts" / "fixtures"
COMMAND = {"operation_id": "11111111-1111-4111-8111-111111111111", "expected_version": 0}


def test_every_frozen_d_route_has_one_pattern_and_all_methods():
    frozen = json.loads((FIXTURES / "routes-v3.json").read_text(encoding="utf8"))
    for entry in (r for r in frozen["routes"] if r["owner"] == "D"):
        path = entry["path"].replace("/api/v1", "")
        replacements = {"pk": "42", "makerspace_id": "9", "public_token": "11111111-2222-4333-8444-555555555555",
                        "entry_public_id": "11111111-2222-4333-8444-555555555556"}
        import re
        path = re.sub(r"\{([^}]+)\}", lambda m: replacements.get(m[1], "1"), path)
        match = resolve(path, urlconf="apps.events.judging.urls")
        assert match.url_name == entry["name"]
        view = match.func.view_class
        for method in entry["operations"]:
            assert hasattr(view, "get" if method == "HEAD" else method.lower())
    assert len({p.name for p in urlpatterns}) == len(urlpatterns)


def test_canonical_sponsor_grant_fixture_is_consumed_without_renaming():
    routes = json.loads((FIXTURES / "routes-v3.json").read_text(encoding="utf8"))["routes"]
    fixture = next(r for r in routes if r["name"] == "events-programme-member-resume-consents")
    values = validated(SponsorGrantInput, fixture["operations"]["POST"]["request_example"])
    assert values["purpose"] == "recruiting" and values["consent"] is True


@pytest.mark.parametrize("change", [{"consent": False}, {"consent": "true"}, {"purpose": "marketing"},
                                     {"member_id": 99}, {"expected_version": True}])
def test_consent_never_infers_owner_or_purpose(change):
    data = {**COMMAND, "sponsor_id": 6, "asset_id": 301, "purpose": "recruiting", "consent": True, "disclosure_revision": 1}
    with pytest.raises((ValidationError, ProgrammeError)):
        validated(SponsorGrantInput, {**data, **change})


@pytest.mark.parametrize("score", [True, "3", 3.0, 0, 6])
def test_score_http_input_is_strict_even_when_drf_would_coerce(score):
    with pytest.raises(ValidationError):
        validated(ScoreInput, {**COMMAND, "scores": {"build": score}})


def test_withdrawal_scope_is_closed_and_requires_owned_item_ids():
    for extra in ({"scope": "all", "asset_ids": [1]}, {"scope": "items"},
                  {"scope": "items", "asset_ids": [1, 1]}, {"scope": "metadata"}):
        with pytest.raises((ValidationError, ProgrammeError)):
            validated(GalleryWithdrawInput, {**COMMAND, **extra})


@pytest.mark.parametrize("header", [None, "different", "22222222-2222-4222-8222-222222222222"])
def test_http_commands_require_the_matching_idempotency_header(header):
    from types import SimpleNamespace
    from apps.events.judging.api_common import PrivateView
    with pytest.raises(ProgrammeError) as error:
        PrivateView.validate_command_header(SimpleNamespace(data=COMMAND, headers={"Idempotency-Key": header}))
    assert error.value.detail["code"] == "invalid_idempotency_key"
