import json
import re
from pathlib import Path
from uuid import UUID
import pytest
from apps.events.contributions import urls_member, urls_admin, urls_public
from apps.events.mentoring import urls_member as mentor_member, urls_admin as mentor_admin
from apps.events.contributions.urls_completion import ADMIN, MEMBER
from apps.events.mentoring.urls_completion import urlpatterns as mentor_completion
from apps.events.contributions.serializers import RoleInputSerializer

FIXTURES = Path(__file__).parents[1] / "contracts" / "fixtures"


def test_every_frozen_c_route_has_one_exact_path_and_method_set():
    fixture = json.loads((FIXTURES / "routes-v3.json").read_text())
    expected = {r["name"]: r for r in fixture["routes"] if r["owner"] == "C"}
    extension = json.loads((FIXTURES.parents[1] / "integration" / "fixtures" / "routes-gf1.json").read_text())
    expected.update({r["name"]: r for r in extension["routes"] if r["owner"] == "C2"})
    # Contract v4 replaces rows changed after G-final part 1; v3 and gf1 bytes stay frozen.
    delta = json.loads((FIXTURES / "routes-v4.json").read_text())
    expected.update({r["name"]: r for r in delta["routes"] if r["owner"] in ("C", "C2")})
    patterns = [*urls_member.urlpatterns, *urls_admin.urlpatterns, *urls_public.urlpatterns,
                *mentor_member.urlpatterns, *mentor_admin.urlpatterns, *ADMIN, *MEMBER, *mentor_completion]
    # R3: G9 (2f9d042d) added the Mentor Desk alert-routes setting after contract v4 froze; it is
    # registered in accounts/programme_route_catalog.py and has its own tests.
    patterns = [p for p in patterns if p.name != "events-programme-admin-mentor-alert-routes"]
    assert len(patterns) == len({p.name for p in patterns}) == len(expected)
    assert {p.name for p in patterns} == set(expected)
    for pattern in patterns:
        cls = pattern.callback.view_class
        actual = {method.upper() for method in cls.http_method_names if method != "options"
            and (hasattr(cls, method) or method == "head" and hasattr(cls, "get"))}
        assert actual == set(expected[pattern.name]["operations"]), pattern.name
        suffix = re.sub(r"<(?:int|uuid):([^>]+)>", r"{\1}", str(pattern.pattern))
        prefix = {"member": "/api/v1/member/", "admin": "/api/v1/admin/", "public": "/api/v1/public/"}[expected[pattern.name]["scope"]]
        assert prefix + suffix == expected[pattern.name]["path"]


@pytest.mark.parametrize("key", ["role", "member_id", "permissions", "state", "sponsor_id", "allow_resume"])
def test_member_form_never_accepts_authority_or_sponsor_consent(key):
    data = {"operation_id": str(UUID(int=1)), "expected_version": 0,
        "form": {"schema_version": 2, "form_id": "mentor-application", "revision": 3},
        "answers": {}, "event_date_revision": 7, key: True}
    serializer = RoleInputSerializer(data=data)
    assert not serializer.is_valid()
    assert key in serializer.errors


def test_shared_role_form_payload_is_not_renested():
    fixture = json.loads((FIXTURES / "routes-v3.json").read_text())
    route = next(r for r in fixture["routes"] if r["name"] == "events-programme-member-role-application-submit")
    serializer = RoleInputSerializer(data=route["operations"]["POST"]["request_example"])
    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data["form"]["schema_version"] == 2
    assert "member_id" not in serializer.validated_data


def test_error_wire_preserves_integer_version_and_conflict_ids():
    from apps.events.contributions.errors import ProgrammeError
    error = ProgrammeError("stale_version", "This changed.", current_version=5,
        conflicts=[{"booking_id": 401}])
    assert type(error.detail["current_version"]) is int
    assert type(error.detail["conflicts"][0]["booking_id"]) is int
