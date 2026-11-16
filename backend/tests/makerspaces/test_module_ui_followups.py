"""MODULE-UI follow-ups: purge URL from the server, matrix template hooks, moduleRoleMap.ts drift guard."""
import re
from pathlib import Path

import pytest
from django.template.loader import render_to_string
from django.urls import reverse

from apps.accounts import rbac_actions
from apps.accounts.models import User
from apps.makerspaces.module_registry import MODULES
from tests.fixed_roles.helpers import staff_account
from tests.return_helpers import authenticated_client, make_space, make_user

ROLE_MAP = Path(__file__).resolve().parents[3] / "frontend" / "src" / "features" / "staff" / "modules" / "moduleRoleMap.ts"
REAL_ACTIONS = {v for k, v in vars(rbac_actions.Action).items() if not k.startswith("_") and isinstance(v, str)}


def _module_actions():
    body = re.search(r"MODULE_ACTIONS[^=]*=\s*\{(.*?)\n\};", ROLE_MAP.read_text(encoding="utf-8"), re.S).group(1)
    return {key: re.findall(r'"([a-z_]+)"', actions)
            for key, actions in re.findall(r"(\w+):\s*\[([^\]]*)\]", body)}


def test_role_map_names_only_real_actions_and_every_module():
    mapped = _module_actions()
    assert set(mapped) == {definition.key for definition in MODULES}, "moduleRoleMap.ts must map every registered module"
    unknown = {(key, a) for key, actions in mapped.items() for a in actions if a not in REAL_ACTIONS}
    assert not unknown, f"not rbac actions: {sorted(unknown)}"


def test_role_map_implied_actions_are_real_and_match_the_backend():
    text = ROLE_MAP.read_text(encoding="utf-8")
    block = re.search(r"const IMPLIED[^=]*=\s*\{(.*?)\n\};", text, re.S).group(1)
    for grant, implied in re.findall(r"(\w+):\s*\[([^\]]*)\]", block):
        assert grant in REAL_ACTIONS
        for action in re.findall(r'"([a-z_]+)"', implied):
            assert action in rbac_actions.expand_implied_actions({grant}), f"{grant} does not imply {action} on the server"


def test_role_map_covers_the_core_actions_module_routes_gate_on():
    # No route->module table exists server-side, so pin the load-bearing pairs explicitly.
    mapped = _module_actions()
    required = {"machines": "manage_machines", "events": "manage_events", "bookings": "manage_bookings", "machine_service": "manage_printing",
                "qr_management": "manage_qr", "evidence_uploads": "upload_evidence", "devices": "manage_devices", "shop": "manage_shop",
                "analytics": "view_analytics", "membership": "manage_members"}
    missing = {k: a for k, a in required.items() if a not in mapped[k]}
    assert not missing


@pytest.mark.django_db
def test_superadmin_gets_the_real_purge_url_and_a_space_manager_does_not():
    space = make_space("purge-url")
    root = make_user("purge-url-root", role=User.Role.SUPERADMIN, access_status=User.AccessStatus.ACTIVE)
    data = authenticated_client(root).get(reverse("admin-module-groups", args=[space.pk])).data
    assert data["capability_purge_url"] == reverse("admin:makerspaces_makerspace_capability_purge", args=[space.pk])
    manager = authenticated_client(staff_account(space, "purge-url-sm", "space_manager"))
    assert manager.get(reverse("admin-module-groups", args=[space.pk])).data["capability_purge_url"] is None


@pytest.mark.django_db
def test_matrix_template_has_search_filter_hooks_and_posts_every_checkbox():
    from apps.makerspaces.admin_capabilities import MakerspaceAdminForm
    form = MakerspaceAdminForm(instance=make_space("matrix-render"))
    html = str(form["capabilities"])
    for hook in ("data-capability-search", 'data-capability-filter="on"', 'data-capability-filter="off"', "data-capability-area",
                 "data-capability-empty", "data-capability-notice", 'id="capability-rules"'):
        assert hook in html, hook
    assert 'name="capabilities" value="module:bookings"' in html and 'name="capabilities" value="feature:bookings.recurring"' in html
    assert render_to_string("admin/makerspaces/capability_matrix.html", {"widget": {"name": "capabilities", "optgroups": []},
                                                                      "capability_rules": {}, "capability_sections": []})
