import ast
import json
from pathlib import Path
from apps.events.hackathons import urls_admin, urls_member, urls_public

ROOT = Path(__file__).parents[5]
FIXTURES = Path(__file__).parents[1] / "contracts" / "fixtures"


def test_exact_frozen_names_and_single_path_for_each_method_set():
    fixture = json.loads((FIXTURES / "routes-v3.json").read_text())
    expected = {row["name"]: row for row in fixture["routes"] if row["owner"] == "A"}
    # Contract v4 adds the part-4 organizer team reads; v3 bytes stay frozen.
    delta = json.loads((FIXTURES / "routes-v4.json").read_text())
    expected.update({row["name"]: row for row in delta["routes"] if row["owner"] == "A"})
    patterns = [*urls_admin.urlpatterns, *urls_member.urlpatterns, *urls_public.urlpatterns]
    assert len(patterns) == len(expected) == len({p.name for p in patterns})
    for pattern in patterns:
        contract = expected[pattern.name]
        cls = pattern.callback.view_class
        for method in contract["operations"]:
            assert hasattr(cls, method.lower()) or method == "HEAD" and hasattr(cls, "get")
        assert str(pattern.pattern).endswith("/")


def test_no_lane_a_production_writer_sets_registration_status():
    root = Path(__file__).parents[4] / "apps" / "events" / "hackathons"
    for path in root.glob("*.py"):
        source = path.read_text()
        assert "EventRegistration.objects.create(" not in source
        assert "registration.status =" not in source
        assert len(source.splitlines()) <= 300
