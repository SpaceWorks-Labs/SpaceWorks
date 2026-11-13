"""#190: the web console searches the audit log across spaces, including platform-level rows."""
import pytest

from apps.audit import services as audit

from .helpers import api, manager, space, superadmin

pytestmark = pytest.mark.django_db
URL = "/api/v1/admin/audit-logs"


def test_platform_only_lists_rows_without_a_space_for_the_superadmin_only():
    lab = space()
    root, boss = superadmin(), manager(lab)
    audit.record(root, "platform.overview_exported", meta={})
    audit.record(boss, "settings.changed", makerspace=lab, target=lab, meta={})
    every = api(root).get(URL).json()["results"]
    assert {row["action"] for row in every} >= {"platform.overview_exported", "settings.changed"}
    platform_rows = api(root).get(URL, {"platform_only": "true"}).json()["results"]
    assert [row["action"] for row in platform_rows] == ["platform.overview_exported"]
    assert api(boss).get(URL, {"platform_only": "true"}).json()["results"] == []
