"""Lane r2-gap-misc, #192 (1): "Hide this space from the platform", independent of a domain.

Local, untracked (#175): run in the test phase on the combined tree. The Space Manager switches it
without any custom domain (through the settings authority, audited); every central listing leaves
the space out; the space stays reachable on its own slug; the superadmin still sees it.
The self-host domain-trust tests live in tests/test_frontend_domain.py (this lane's updated copy).
"""
import uuid

import pytest
from django.test import RequestFactory, override_settings
from rest_framework.test import APIClient

from apps.accounts import rbac
from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.makerspaces.models import Makerspace
from apps.makerspaces.website_directory import directory_spaces, sitemap_spaces
from tests.return_helpers import authenticated_client, make_member, make_space, make_user

pytestmark = pytest.mark.django_db


def spaces(prefix):
    shown = make_space(f"{prefix}-shown-{uuid.uuid4().hex[:6]}")
    hidden = make_space(f"{prefix}-hidden-{uuid.uuid4().hex[:6]}")
    for row in (shown, hidden):
        row.enabled_modules = sorted(set(row.enabled_modules or []) | {"events"})
        row.public_site_enabled = True
        row.public_inventory_enabled = True
        row.save(update_fields=["enabled_modules", "public_site_enabled", "public_inventory_enabled"])
    manager = make_member(f"{prefix}-sm-{uuid.uuid4().hex[:6]}", hidden)
    response = authenticated_client(manager).patch(f"/api/v1/admin/makerspaces/{hidden.pk}",
                                                   {"hidden_from_central_directory": True}, format="json")
    assert response.status_code == 200, response.data
    hidden.refresh_from_db()
    assert hidden.hidden_from_central_directory is True and not hidden.frontend_domain
    return shown, hidden, manager


def test_the_toggle_works_without_a_domain_and_is_audited():
    _shown, hidden, manager = spaces("hide-audit")
    row = AuditLog.objects.filter(action="settings.changed", makerspace=hidden).latest("pk")
    assert row.actor_id == manager.pk
    assert row.meta == {"module": "public_site", "key": "hidden_from_central_directory", "from": False, "to": True,
                        "via": "space_manager", "grant_id": None}


def test_a_no_op_save_writes_no_audit_row():
    _shown, hidden, manager = spaces("hide-noop")
    before = AuditLog.objects.filter(action="settings.changed", makerspace=hidden).count()
    authenticated_client(manager).patch(f"/api/v1/admin/makerspaces/{hidden.pk}",
                                        {"hidden_from_central_directory": True}, format="json")
    assert AuditLog.objects.filter(action="settings.changed", makerspace=hidden).count() == before


def test_the_public_space_list_leaves_it_out():
    shown, hidden, _manager = spaces("hide-list")
    slugs = {row["slug"] for row in APIClient().get("/api/v1/public/makerspaces/").json()}
    assert shown.slug in slugs and hidden.slug not in slugs


def test_discover_search_and_the_sitemap_leave_it_out():
    shown, hidden, _manager = spaces("hide-discover")
    listed = set(directory_spaces().values_list("pk", flat=True))
    assert shown.pk in listed and hidden.pk not in listed
    # The test environment leaves PUBLIC_APP_BASE_URL empty, so sitemap_spaces 404s every host; pin it.
    request = RequestFactory().get("/sitemap.xml", HTTP_HOST="spaceworks.test")
    with override_settings(ALLOWED_HOSTS=["*"], PUBLIC_APP_BASE_URL="https://spaceworks.test"):
        mapped = set(sitemap_spaces(request).values_list("pk", flat=True))
    assert hidden.pk not in mapped


def test_central_event_partner_listing_leaves_it_out_for_outsiders():
    from apps.events.directories import partner_makerspaces
    shown, hidden, manager = spaces("hide-partner")
    outsider = make_member(f"hide-partner-out-{uuid.uuid4().hex[:6]}", shown)
    listed = set(partner_makerspaces(outsider).values_list("pk", flat=True))
    assert shown.pk in listed and hidden.pk not in listed
    assert hidden.pk in set(partner_makerspaces(manager).values_list("pk", flat=True))  # its own staff still see it


def test_the_organization_catalogue_leaves_it_out():
    from apps.organizations.public_catalog import linked_spaces_for
    from apps.organizations.models import Organization
    _shown, hidden, _manager = spaces("hide-org")
    organization = Organization.objects.filter(public_profile_enabled=True, is_active=True).first()
    if organization is None:
        pytest.skip("No public organization fixture in this database")
    assert hidden.pk not in set(linked_spaces_for(organization).values_list("pk", flat=True))


def test_it_stays_reachable_on_its_own_slug():
    _shown, hidden, _manager = spaces("hide-reach")
    response = APIClient().get(f"/api/v1/public/{hidden.slug}/inventory/")
    assert response.status_code == 200, response.content


def test_the_superadmin_still_sees_it():
    _shown, hidden, _manager = spaces("hide-root")
    root = make_user(f"hide-root-{uuid.uuid4().hex[:6]}", role=User.Role.SUPERADMIN)
    rows = rbac.scope_by_action(root, rbac.Action.MANAGE_MAKERSPACE, Makerspace.objects.all(), field="pk")
    assert rows.filter(pk=hidden.pk).exists()
    assert authenticated_client(root).get(f"/api/v1/admin/makerspaces/{hidden.pk}").status_code == 200
    from apps.operations.platform_overview import build_platform_overview
    from apps.operations.platform_overview_window import resolve_window
    overview = build_platform_overview(resolve_window("all_time"), include_excluded=True)
    assert hidden.pk in {row["id"] for row in overview["spaces"]}


def test_a_staff_member_without_space_manager_authority_cannot_hide_it():
    space = make_space(f"hide-im-{uuid.uuid4().hex[:6]}")
    inventory_manager = make_member(f"hide-im-user-{uuid.uuid4().hex[:6]}", space,
                                    membership_role="inventory_manager", role=User.Role.REQUESTER)
    response = authenticated_client(inventory_manager).patch(
        f"/api/v1/admin/makerspaces/{space.pk}", {"hidden_from_central_directory": True}, format="json")
    assert response.status_code in (403, 404)
    space.refresh_from_db()
    assert space.hidden_from_central_directory is False
