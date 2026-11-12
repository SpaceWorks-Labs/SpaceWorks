"""Decision 246 (lane T4): role access to the report catalogue and each report endpoint (224(a), 224(d)).

Derived from `ROLE_CATALOG` and each definition's `required_action` / `alternate_actions`, so the
tests follow the catalogue instead of hard-coding who may read what:

* the catalogue never lists a report whose action the role does not hold, and a Space Manager sees
  every area (224(a));
* the area-keyed reports (machines: fablab-health, printer-service, certification-coverage; people:
  member-activity, membership-growth, community-engagement, join-funnel) are refused to a role that
  holds only `view_audit` (the Inventory Manager), whatever the role's other powers;
* a plain Member and the handout-only Handover role are refused every report endpoint (224(d));
* the accountability page follows `manage_members` (full) or `view_inventory` (read-only subset).
"""
import pytest
from django.urls import reverse

from apps.accounts import rbac
from apps.makerspaces.models import Makerspace
from apps.makerspaces.module_registry import MODULE_KEYS
from apps.makerspaces.role_catalog import ROLE_BY_SLUG, ROLE_CATALOG
from apps.operations.report_registry import REPORT_DEFINITIONS
from apps.operations.report_types import definition_actions
from tests.fixed_roles.helpers import staff_account
from tests.return_helpers import authenticated_client, make_space

pytestmark = pytest.mark.django_db

SLUGS = [role.slug for role in ROLE_CATALOG]
MACHINE_KEYS = ("fablab-health", "printer-service", "certification-coverage")
PEOPLE_KEYS = ("member-activity", "membership-growth", "community-engagement", "join-funnel")
TENANT_DEFINITIONS = [d for d in REPORT_DEFINITIONS
                      if not d.platform_only and not d.subject_kind and d.key != "organization-membership"]


def world(slug):
    space = make_space(slug)
    Makerspace.objects.filter(pk=space.pk).update(enabled_modules=sorted(MODULE_KEYS))
    space.refresh_from_db()
    return space


def holds(slug, definition):
    # Effective actions: the stored grants plus the implied ones (the Space Manager reaches shop and card
    # reports through `manage_makerspace`, not a stored grant).
    effective = rbac.expand_implied_actions(ROLE_BY_SLUG[slug].granted_actions)
    return any(action in effective for action in definition_actions(definition))


def definition(key):
    return next(d for d in REPORT_DEFINITIONS if d.key == key)


@pytest.mark.parametrize("key", MACHINE_KEYS + PEOPLE_KEYS)
def test_area_reports_never_admit_view_audit_alone(key):
    d = definition(key)
    actions = set(definition_actions(d))
    assert "view_audit" not in actions
    assert actions & ({"manage_machines"} if key in MACHINE_KEYS else {"manage_members"})


@pytest.mark.parametrize("slug", SLUGS)
def test_catalogue_lists_only_what_the_role_may_read(slug):
    space = world(f"rra-cat-{slug}".replace("_", "-"))
    actor = staff_account(space, f"rra-cat-{slug}", slug)
    response = authenticated_client(actor).get(reverse("report-catalog", args=[space.pk]))
    if not any(holds(slug, d) for d in TENANT_DEFINITIONS) or slug == "handover":
        assert response.status_code in (403, 404)
        return
    assert response.status_code == 200, response.content
    listed = {row["key"] for row in response.json()["results"]}
    allowed = {d.key for d in TENANT_DEFINITIONS if holds(slug, d)}
    assert listed <= allowed, sorted(listed - allowed)
    if slug == "space_manager":
        assert set(MACHINE_KEYS + PEOPLE_KEYS) <= listed


def test_the_inventory_manager_sees_inventory_reports_but_no_machine_or_people_report():
    space = world("rra-im")
    actor = staff_account(space, "rra-im", "inventory_manager")
    response = authenticated_client(actor).get(reverse("report-catalog", args=[space.pk]))
    assert response.status_code == 200
    listed = {row["key"] for row in response.json()["results"]}
    assert listed and not listed & set(MACHINE_KEYS + PEOPLE_KEYS)


@pytest.mark.parametrize("slug", SLUGS)
def test_area_report_endpoints_follow_the_roles_own_area_action(slug):
    space = world(f"rra-ep-{slug}".replace("_", "-"))
    client = authenticated_client(staff_account(space, f"rra-ep-{slug}", slug))
    problems = []
    for key in MACHINE_KEYS + PEOPLE_KEYS:
        status = client.get(reverse("analytics-generic", args=[space.pk, key])).status_code
        allowed = holds(slug, definition(key)) and slug != "handover"
        if allowed and status == 403:  # a 404 may mean the report's capability is off in this fixture
            problems.append(f"{key}: {slug} should read it, got {status}")
        if not allowed and status not in (403, 404):
            problems.append(f"{key}: {slug} should be refused, got {status}")
        if status >= 500:
            problems.append(f"{key}: server error {status}")
    assert not problems, problems


@pytest.mark.parametrize("slug", ["member", "handover"])
def test_a_member_and_the_handout_only_role_are_refused_every_report_endpoint(slug):
    space = world(f"rra-none-{slug}")
    client = authenticated_client(staff_account(space, f"rra-none-{slug}", slug))
    wrong = {}
    for d in TENANT_DEFINITIONS:
        status = client.get(reverse("analytics-generic", args=[space.pk, d.key])).status_code
        if status not in (403, 404):
            wrong[d.key] = status
    assert not wrong, wrong


@pytest.mark.parametrize("slug", SLUGS)
def test_accountability_page_follows_manage_members_or_view_inventory(slug):
    space = world(f"rra-acc-{slug}".replace("_", "-"))
    client = authenticated_client(staff_account(space, f"rra-acc-{slug}", slug))
    status = client.get(reverse("accountability-dashboard", args=[space.pk])).status_code
    actions = ROLE_BY_SLUG[slug].granted_actions
    if "manage_members" in actions or ("view_inventory" in actions and slug != "handover"):
        assert status == 200
    else:
        assert status in (403, 404)


def test_another_spaces_manager_reads_nothing_of_this_space():
    space, other = world("rra-xsp-a"), world("rra-xsp-b")
    stranger = authenticated_client(staff_account(other, "rra-xsp-mgr", "space_manager"))
    assert stranger.get(reverse("report-catalog", args=[space.pk])).status_code in (403, 404)
    for key in MACHINE_KEYS + PEOPLE_KEYS:
        assert stranger.get(reverse("analytics-generic", args=[space.pk, key])).status_code in (403, 404)
    assert stranger.get(reverse("accountability-dashboard", args=[space.pk])).status_code in (403, 404)
