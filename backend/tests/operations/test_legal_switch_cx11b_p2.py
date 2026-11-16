"""Own legal pages fall back while off; saved Markdown survives and editing resumes."""
import pytest

from apps.operations.legal_pages import resolve, set_platform_page, set_space_override
from tests.accounts.account_factories import make_staff
from tests.modules.switch_matrix_helpers import MODULE_KEYS, live_space
from tests.modules.switch_matrix_object_helpers import client_for
from tests.payments.switch_helpers_cx11b_p2 import read_policy_cycle, route_cycle

pytestmark = [pytest.mark.django_db, pytest.mark.area_frontend_shell, pytest.mark.area_platform]


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
def test_legal_switch_preserves_space_copy_and_restores_writes(native):
    space = live_space("p2-legal", MODULE_KEYS)
    actor = make_staff(space, username="p2-legal-manager", access_status="active")
    platform = set_platform_page("terms", "", "# Platform terms")
    set_space_override(space, "terms", "# Retained space terms")
    # Parentless policy: unrelated optional modules have no say in the fallback.
    def read():
        from apps.makerspaces.models import Makerspace
        assert Makerspace.objects.get(pk=space.pk).branding_config["legal_pages"]["terms"] == "# Retained space terms"
        page = resolve("terms", makerspace=space, language="en")
        return page["source"], page["markdown"]
    # Snapshot branding alone: enabled_features is intentionally changed by this test.
    read_policy_cycle(space, {"platform": platform}, "legal.space_pages", read,
        ("space", "# Retained space terms"), ("platform", "# Platform terms"))
    route_cycle(space, client_for(actor, space, native), {"platform": platform}, "legal.space_pages",
        f"/api/v1/admin/makerspace/{space.pk}/legal-pages/terms", method="put",
        body={"markdown": "# Changed space terms"}, off=(404, "not_found"))
    space.refresh_from_db()
    assert space.branding_config["legal_pages"]["terms"] == "# Changed space terms"
