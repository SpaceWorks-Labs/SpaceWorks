"""Lane URL lists must match the G checkpoint; runtime mounting is G-owned."""
import json
from pathlib import Path
import re

from apps.events.submissions.urls_member import urlpatterns as member
from apps.events.submissions.urls_admin import urlpatterns as admin
from apps.events.submissions.urls_public import urlpatterns as public


def test_every_frozen_lane_b_named_path_exists_once():
    path = Path(__file__).parents[1] / "contracts/fixtures/routes-v3.json"
    fixture = json.loads(path.read_text())
    rows = fixture["routes"] if isinstance(fixture, dict) else fixture
    expected = {r["name"]: r["path"] for r in rows if r["owner"] == "B"}
    # Contract v4 adds the part-4 organizer submission reads; v3 bytes stay frozen.
    delta = json.loads((path.parent / "routes-v4.json").read_text())
    expected.update({r["name"]: r["path"] for r in delta["routes"] if r["owner"] == "B"})
    actual = {}
    for prefix, patterns in (("member/", member), ("admin/", admin), ("public/", public)):
        for pattern in patterns:
            assert pattern.name not in actual
            relative = re.sub(r"<(?:int|uuid):([^>]+)>", r"{\1}", str(pattern.pattern))
            actual[pattern.name] = "/api/v1/" + prefix + relative
    # R3: routes added after contract v4 froze (submit-content #179 stages and shortlists, L21b
    # integrity, hack-money team charges) are allowed only when the live programme route
    # catalogue registers them; every frozen row must still exist exactly.
    from apps.accounts.programme_route_catalog import BY_NAME as registered
    later = {name for name in actual if name not in expected}
    assert later <= set(registered), sorted(later - set(registered))
    assert {name: actual[name] for name in expected if name in actual} == expected
