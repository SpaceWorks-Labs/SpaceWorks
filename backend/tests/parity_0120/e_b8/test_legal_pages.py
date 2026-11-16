"""E-B8: privacy / terms defaults, platform override, per-space override, public read and audit."""
import pytest
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.operations import legal_pages
from tests.audit_explorer_helpers import superadmin
from tests.return_helpers import authenticated_client, make_member, make_space

pytestmark = pytest.mark.django_db


def test_defaults_are_served_anonymously_for_both_pages():
    for slug in ("privacy", "terms"):
        res = APIClient().get(f"/api/v1/discover/legal/{slug}/")
        assert res.status_code == 200
        assert res.json()["source"] == "default" and res.json()["markdown"].startswith("# ")
    assert APIClient().get("/api/v1/discover/legal/cookies/").status_code == 404


def test_platform_override_then_reset_and_audit():
    client = authenticated_client(superadmin("eb8-root"))
    put = client.put("/api/v1/admin/platform/legal-pages/privacy", {"markdown": "# Ours\n\nText."}, format="json")
    assert put.status_code == 200 and put.json()["source"] == "platform"
    assert APIClient().get("/api/v1/discover/legal/privacy/").json()["markdown"].startswith("# Ours")
    blank = client.put("/api/v1/admin/platform/legal-pages/privacy", {"markdown": "  "}, format="json")
    assert blank.status_code == 400
    assert client.delete("/api/v1/admin/platform/legal-pages/privacy").status_code == 204
    assert APIClient().get("/api/v1/discover/legal/privacy/").json()["source"] == "default"
    metas = [row.meta for row in AuditLog.objects.filter(action="platform.legal_page_updated").order_by("pk")]
    assert [m["action"] for m in metas] == ["set", "reset"] and "Ours" not in str(metas)


def test_platform_pages_are_superadmin_only():
    staff = authenticated_client(make_member("eb8-legal-sm", make_space("eb8-legal-auth")))
    res = staff.put("/api/v1/admin/platform/legal-pages/terms", {"markdown": "x"}, format="json")
    assert res.status_code in (401, 403)


def test_space_override_wins_for_that_space_only_and_can_be_cleared():
    space, other = make_space("eb8-legal-a"), make_space("eb8-legal-b")
    client = authenticated_client(make_member("eb8-legal-a-sm", space))
    url = f"/api/v1/admin/makerspace/{space.pk}/legal-pages/terms"
    assert client.put(url, {"markdown": "# Our rules"}, format="json").json()["source"] == "space"
    assert APIClient().get(f"/api/v1/discover/legal/terms/?space={space.slug}").json()["markdown"] == "# Our rules"
    assert APIClient().get(f"/api/v1/discover/legal/terms/?space={other.slug}").json()["source"] == "default"
    assert client.put(url, {"markdown": ""}, format="json").json()["source"] == "default"
    cross = f"/api/v1/admin/makerspace/{other.pk}/legal-pages/terms"
    assert client.put(cross, {"markdown": "no"}, format="json").status_code in (403, 404)


def test_clean_markdown_strips_nul_and_normalises_newlines():
    assert legal_pages.clean_markdown("a\x00b\r\nc ") == "ab\nc"
