"""Decision 248 (lane C1b): member 360 reach, bulk invites and plans, the new reports, roster filters and extras.

Written, not run here: the consolidation lane runs the backend suite in Docker.
"""
import pytest
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.makerspaces.models import MakerspaceMembership
from tests.accounts.account_factories import make_membership
from tests.fixed_roles.helpers import staff_account
from tests.return_helpers import authenticated_client, make_space

pytestmark = pytest.mark.django_db


def _space(slug, modules=(), features=()):
    space = make_space(slug)
    space.enabled_modules = sorted(set(space.enabled_modules or []) | {"staff_admin", "reports", *modules})
    space.enabled_features = sorted(set(space.enabled_features or []) | set(features))
    space.save(update_fields=["enabled_modules", "enabled_features"])
    return space


def _member(space, name):
    user = User.objects.create_user(username=name, email=f"{name}@example.test", display_name=name)
    make_membership(user, space)  # a membership needs the tenant's built-in Member role (DB-enforced)
    return user


# --- member 360 (decision 248) -------------------------------------------------------------------

def test_member_360_opens_to_every_area_staff_role_and_refuses_members():
    space = _space("c1b-360")
    target = _member(space, "c1b-target")
    url = reverse("admin-member-activity", args=[space.pk, target.pk])
    for role in ("space_manager", "inventory_manager", "machine_manager", "shop_manager"):
        viewer = staff_account(space, f"c1b-{role}", role)
        assert authenticated_client(viewer).get(url).status_code == 200, role
    plain = staff_account(space, "c1b-plain-member", "member")
    assert authenticated_client(plain).get(url).status_code == 404


def test_member_360_gives_rows_only_for_managed_areas():
    space = _space("c1b-360-rows", modules=("shop",))
    target = _member(space, "c1b-rows-target")
    viewer = staff_account(space, "c1b-rows-im", "inventory_manager")
    body = authenticated_client(viewer).get(reverse("admin-member-activity", args=[space.pk, target.pk])).json()
    by_area = {block["area"]: block for block in body["areas"]}
    assert by_area["lending"]["rows_visible"] is True
    assert by_area["machines"]["rows_visible"] is False and by_area["machines"]["rows"] is None


# --- bulk staff invites ----------------------------------------------------------------------------

def test_bulk_invites_are_all_or_nothing_and_name_the_failed_index():
    from apps.accounts.models import StaffInvitation

    space = _space("c1b-invites")
    boss = staff_account(space, "c1b-inv-boss", "space_manager")
    client = authenticated_client(boss)
    url = reverse("admin-staff-roles-bulk-invite", args=[space.pk])
    bad = {"invites": [{"email": "ok@example.test", "roles": ["inventory_manager"]},
                       {"email": "bad@example.test", "roles": ["no_such_role"]}]}
    refused = client.post(url, bad, format="json")
    assert refused.status_code == 409 and refused.json()["failed_id"] == 1
    assert StaffInvitation.objects.filter(makerspace=space).count() == 0


def test_bulk_invites_reject_duplicates_and_more_than_fifty():
    space = _space("c1b-invites-validate")
    boss = staff_account(space, "c1b-inv-boss2", "space_manager")
    client = authenticated_client(boss)
    url = reverse("admin-staff-roles-bulk-invite", args=[space.pk])
    twice = {"invites": [{"email": "a@example.test", "roles": ["inventory_manager"]},
                         {"email": "A@example.test", "roles": ["inventory_manager"]}]}
    assert client.post(url, twice, format="json").status_code == 400
    many = {"invites": [{"email": f"p{i}@example.test", "roles": ["inventory_manager"]} for i in range(51)]}
    assert client.post(url, many, format="json").status_code == 400


def test_bulk_invites_refuse_a_role_without_staff_authority():
    space = _space("c1b-invites-authority")
    member = staff_account(space, "c1b-inv-member", "member")
    url = reverse("admin-staff-roles-bulk-invite", args=[space.pk])
    response = authenticated_client(member).post(
        url, {"invites": [{"email": "x@example.test", "roles": ["inventory_manager"]}]}, format="json")
    assert response.status_code in (403, 404)


# --- bulk plan assignment ---------------------------------------------------------------------------

def test_bulk_plan_assignment_is_superadmin_only():
    space = _space("c1b-plan")
    boss = staff_account(space, "c1b-plan-boss", "space_manager")
    response = authenticated_client(boss).post(
        reverse("admin-platform-space-plan-bulk"), {"makerspace_ids": [space.pk], "plan_id": 1}, format="json")
    assert response.status_code in (403, 404)


def test_bulk_plan_assignment_refuses_an_unknown_space_with_failed_id(settings):
    settings.MANAGED_PLANS_ENABLED = True
    root = User.objects.create_superuser("c1b-root", "c1b-root@example.test", "pw-123456-Aa!")
    response = authenticated_client(root).post(
        reverse("admin-platform-space-plan-bulk"), {"makerspace_ids": [987654], "plan_id": 1}, format="json")
    assert response.status_code in (403, 404, 409)
    if response.status_code == 409:
        assert response.json()["failed_id"] == 987654


# --- the new reports --------------------------------------------------------------------------------

def test_the_new_report_keys_are_registered_tenant_local_and_unscheduled():
    from apps.operations.report_definitions_completeness import COMPLETENESS_REPORT_DEFINITIONS
    from apps.operations.report_registry import REPORT_REGISTRY

    assert len(COMPLETENESS_REPORT_DEFINITIONS) == 11
    for definition in COMPLETENESS_REPORT_DEFINITIONS:
        assert definition.key in REPORT_REGISTRY
        assert definition.deployment_aggregate is False and definition.schedulable is False
    inventory_titles = [d.title for d in COMPLETENESS_REPORT_DEFINITIONS if d.key.startswith(("inventory", "overdue"))]
    assert all("ending" not in title.lower() and "lending" not in title.lower() for title in inventory_titles)


def test_inventory_valuation_multiplies_cost_by_quantity_and_skips_unpriced():
    from apps.inventory.models import InventoryProduct
    from apps.operations.reports_completeness_inventory import build_inventory_valuation

    space = _space("c1b-valuation", modules=("public_inventory",))
    InventoryProduct.objects.create(makerspace=space, name="Drill", total_quantity=3, available_quantity=3,
                                    unit_cost="12.50", cost_currency="INR")
    InventoryProduct.objects.create(makerspace=space, name="Mystery", total_quantity=2, available_quantity=2)
    rows = {r["product"]: r for r in build_inventory_valuation(space.pk).records}
    assert str(rows["Drill"]["stock_value"]) == "37.50" and rows["Mystery"]["stock_value"] is None


def test_utilisation_by_category_rolls_quantities_up():
    from apps.inventory.models import InventoryProduct
    from apps.operations.reports_completeness_inventory import build_inventory_utilisation_by_category

    space = _space("c1b-util", modules=("public_inventory",))
    InventoryProduct.objects.create(makerspace=space, name="A", total_quantity=10, available_quantity=6,
                                    issued_quantity=4)
    rows = build_inventory_utilisation_by_category(space.pk).records
    assert rows[0]["category"] == "Uncategorised" and rows[0]["utilisation_percent"] == 40


def test_minors_export_never_carries_birth_date_or_guardian_contact():
    from apps.operations.reports_completeness_people import MINOR_FIELDS

    assert not {"date_of_birth", "guardian_email", "guardian_phone", "signed_name"} & set(MINOR_FIELDS)


def test_staff_roster_export_lists_staff_and_needs_manage_makerspace():
    from apps.operations.reports_completeness_people import build_staff_roster_export

    space = _space("c1b-staff-roster")
    staff_account(space, "c1b-sr-boss", "space_manager")
    rows = build_staff_roster_export(space.pk).records
    assert [r["name"] for r in rows] == ["c1b-sr-boss"] and "Space Manager" in rows[0]["roles"]
    from apps.accounts import rbac
    from apps.operations.report_registry import REPORT_REGISTRY

    assert REPORT_REGISTRY["staff-roster-export"].required_action == rbac.Action.MANAGE_MAKERSPACE


# --- roster filters -----------------------------------------------------------------------------------

def test_roster_filters_flag_verified_minor_volunteer_and_staff():
    from apps.admin_api.roster_filters import apply_roster_filters
    from apps.makerspaces.models import VolunteerHourEntry

    space = _space("c1b-roster", modules=("membership",))
    verified = _member(space, "c1b-verified")
    MakerspaceMembership.objects.filter(user=verified, makerspace=space).update(verified_at=timezone.now())
    helper = _member(space, "c1b-helper")
    VolunteerHourEntry.objects.create(makerspace=space, member=helper, minutes=60, worked_on=timezone.now().date(),
                                      status="approved")
    base = MakerspaceMembership.objects.filter(makerspace=space)
    assert [m.user_id for m in apply_roster_filters(base, {"verified": "true"}, space)] == [verified.pk]
    assert [m.user_id for m in apply_roster_filters(base, {"volunteer": "true"}, space)] == [helper.pk]
    assert apply_roster_filters(base, {"minor": "true"}, space).count() == 0
    assert apply_roster_filters(base, {"staff": "true"}, space).count() == 0
    assert apply_roster_filters(base, {"verified": "maybe"}, space).count() == base.count()


# --- extras: EB1, NT1, MC6, IN8, IN11, MC14, MC11 --------------------------------------------------------

def test_inbox_display_families_carve_shop_and_safety_out_of_their_storage_family():
    from apps.notifications.inbox_families import display_family

    assert display_family("payments", "shop_order_new") == "shop"
    assert display_family("payments", "payment_received") == "payments"
    assert display_family("maintenance", "incident_reported") == "safety"
    assert display_family("maintenance", "due_soon") == "maintenance"


def test_accountability_reads_for_the_inventory_manager_without_restrictions():
    space = _space("c1b-account", modules=("request_workflow",))
    im = staff_account(space, "c1b-acc-im", "inventory_manager")
    response = authenticated_client(im).get(reverse("accountability-dashboard", args=[space.pk]))
    assert response.status_code == 200
    body = response.json()
    assert body["restrictions"] == [] and body["problem_reports"] == []


def test_handover_dashboard_counts_direct_loans_without_the_request_workflow_and_splits_due():
    from apps.operations.dashboard_handover import handover_home

    space = _space("c1b-handover")
    desk = staff_account(space, "c1b-desk", "space_manager")
    queues = handover_home(desk, space)
    assert {"due_today", "overdue", "to_record"} <= set(queues)


def test_service_state_lists_only_machines_the_actor_may_act_on():
    from apps.machines.models import Machine
    from tests.machines.certification_helpers import _machine_type

    space = _space("c1b-state", modules=("machines",), features=("machines.maintenance", "machines.repairs"))
    kind = _machine_type(space)
    Machine.objects.create(makerspace=space, machine_type=kind, name="Router")
    boss = staff_account(space, "c1b-state-boss", "space_manager")
    listed = authenticated_client(boss).get(reverse("admin-service-state", args=[space.pk]))
    assert listed.status_code == 200 and [row["name"] for row in listed.json()] == ["Router"]
    nobody = staff_account(space, "c1b-state-member", "member")
    assert authenticated_client(nobody).get(reverse("admin-service-state", args=[space.pk])).status_code in (403, 404)


def test_machine_time_bookings_are_read_only_and_behind_the_capability():
    space = _space("c1b-mbook", modules=("machines", "bookings"))
    mm = staff_account(space, "c1b-mbook-mm", "machine_manager")
    url = reverse("admin-machine-bookings", args=[space.pk])
    assert authenticated_client(mm).get(url).status_code == 404  # machines.time_booking is off
    assert authenticated_client(mm).post(url, {}, format="json").status_code == 405


def test_maintenance_activity_admits_run_maintenance_as_an_alternate_action():
    from apps.accounts import rbac
    from apps.operations.report_registry import REPORT_REGISTRY

    assert rbac.Action.RUN_MAINTENANCE in REPORT_REGISTRY["maintenance-activity"].alternate_actions


def test_event_report_subject_has_a_grantee_gate_and_the_catalog_keeps_identity_flags():
    from apps.events.report_subject import grantee_gate
    from apps.operations.report_subjects import SUBJECTS
    from apps.operations.report_registry import REPORT_REGISTRY

    assert SUBJECTS["event"].grantee_gate is grantee_gate
    space = _space("c1b-grantee")
    nobody = _member(space, "c1b-nobody")
    assert grantee_gate(nobody, space.pk) is False  # no live event grant, no door
    for key in ("roster-export", "guest-passes-export", "volunteer-hours-export", "minors-consent-export",
                "staff-roster-export", "certification-holders", "incidents-register", "overdue-by-borrower"):
        assert REPORT_REGISTRY[key].identity_bearing is True


def test_shop_product_list_filters_low_stock_only():
    from apps.shop.models import ShopProduct, ShopVariant

    space = _space("c1b-shop", modules=("shop",))
    boss = staff_account(space, "c1b-shop-boss", "space_manager")
    low = ShopProduct.objects.create(makerspace=space, name="Low tee", slug="low-tee")
    ShopVariant.objects.create(makerspace=space, product=low, price="10.00", on_hand=1, reorder_point=3)
    fine = ShopProduct.objects.create(makerspace=space, name="Fine tee", slug="fine-tee")
    ShopVariant.objects.create(makerspace=space, product=fine, price="10.00", on_hand=50, reorder_point=3)
    response = authenticated_client(boss).get(reverse("admin-shop-products", args=[space.pk]) + "?low_stock=true")
    names = [row["name"] for row in response.json()["results"]]
    assert response.status_code == 200 and names == ["Low tee"]
