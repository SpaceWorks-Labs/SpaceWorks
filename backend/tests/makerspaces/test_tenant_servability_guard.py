"""AST guard for archived-style tenant exclusions.

This guard sees statically written ``archived_at`` attributes/lookups and calls to the
known archived-ID helpers in Python files under ``apps/``. It cannot see dynamically
constructed ORM lookup names, raw SQL, or policy implemented outside Python, so those
still require review and behavioural tests.
"""

import ast
from dataclasses import dataclass
from pathlib import Path

import apps.makerspaces


APPS_DIR = Path(apps.makerspaces.__file__).resolve().parent.parent
ARCHIVE_HELPERS = {"archived_makerspace_ids", "_exclude_archived_ids"}
SERVABILITY_CALLS = {
    "is_servable",
    "servable_q",
    "servable_queryset",
    "unservable_makerspace_ids",
    "archived_or_inactive_makerspace_ids",
    *ARCHIVE_HELPERS,
}

# These operations deliberately need rows that normal traffic must not serve.
EXEMPTIONS = {
    # The policy implementation necessarily contains the raw fields it centralizes.
    ("makerspaces/servability.py", "is_servable"),
    ("makerspaces/servability.py", "archived_or_inactive_makerspace_ids"),
    # This status-only boundary deliberately finds paused rows without serving their data.
    ("makerspaces/servability.py", "public_availability_queryset"),
    # Archive recovery must inspect and clear archived_at, and purge must inspect it.
    ("makerspaces/lifecycle_archive.py", "unarchive"),
    ("makerspaces/lifecycle_purge.py", "purge"),
    # /control/ is the superadmin recovery surface for archived/import-failed rows.
    ("makerspaces/admin.py", "ArchivedFilter.queryset"),
    ("makerspaces/admin.py", "MakerspaceAdmin.has_delete_permission"),
    ("makerspaces/admin.py", "MakerspaceAdmin.archived"),
    # Members may discover old charges only after a tenant has actually been archived.
    ("payments/views_member.py", "ArchivedPaymentDiscoveryView.get"),
    # The abort-recovery twin of `unarchive`: cutover archives the source, so reopening
    # it after a failed migration must both inspect and clear `archived_at`. Routing it
    # through the servability policy would make the one operation that undoes a cutover
    # refuse to run on the only state it is ever called in. It is not a hole -- it
    # requires a superuser, a locked pairing, and a verified single-use abort receipt
    # from the target proving it reached ABORTED and can no longer activate.
    ("tenant_migration/cutover.py", "reopen_source"),
    # Release 2 L4: these read a MEMBERSHIP PLAN's or TITLE's own `archived_at` (a retired
    # plan or title), never the makerspace's; the tenant is gated elsewhere on each path.
    ("admin_api/bulk_import_members.py", "existing_state"),
    ("admin_api/views_membership_plan_archive.py", "_set_archived"),
    ("makerspaces/membership_admission_plans.py", "resolve_join"),
    ("makerspaces/membership_admission_settings.py", "plan_feature_needs"),
    ("makerspaces/membership_import_accept.py", "_open_term"),
    ("makerspaces/membership_invite_links.py", "create_link"),
    ("makerspaces/membership_plan_policy.py", "listed_plans"),
    ("makerspaces/membership_plan_services.py", "create_term"),
    ("makerspaces/membership_titles.py", "assign"),
    ("makerspaces/membership_titles.py", "primary_title"),
    ("makerspaces/membership_titles.py", "set_archived"),
    ("makerspaces/models_membership_plans.py", "MembershipPlan.listed"),
    ("makerspaces/views_public_plans.py", "PublicInviteLinkView.get"),
    # Release 2 L15: a PRICE DISCOUNT rule's own `archived_at` (a retired rule kept for frozen
    # quotes), not tenant archival; the views are already makerspace-scoped and servable.
    ("payments/pricing/discount_services.py", "archive_discount"),
    ("payments/pricing/discount_services.py", "update_discount"),
    ("payments/pricing/discounts.py", "candidates"),
    ("payments/views_pricing_discounts.py", "DiscountListView.get"),
    # Release 2 L21a: an EVENT CHECK-IN LIST's own `archived_at` (a retired desk list); the event
    # and its makerspace are resolved and gated by the check-in surface first.
    ("events/checkin_lists.py", "project"),
    ("events/checkin_lists.py", "scan"),
    ("events/checkin_lists.py", "update"),
    # Parity E-B5: list upkeep reads the same list-level `archived_at`.
    ("events/checkin_lists.py", "_check_quota"),
    ("events/checkin_lists.py", "reorder"),
    ("events/checkin_lists.py", "undo"),
    ("events/staff_list_guests.py", "list_columns"),
    ("managed_hosting/extra_quota_counters.py", "checkin_lists"),
    # Release 2 L18: a SPONSOR's own `archived_at` (a retired sponsor kept for its charges and perks);
    # every path is makerspace-scoped and behind the donations surface's servable tenant.
    ("payments/donations/reports_sponsors.py", "_perk_rows"),
    ("payments/donations/sponsors.py", "archive_sponsor"),
    ("payments/donations/tasks.py", "due_perk_ids"),
    ("payments/donations/views_sponsors.py", "PerkListView.post"),
    ("payments/donations/views_sponsors.py", "SponsorListView.get"),
    ("payments/donations/wall.py", "live_sponsors"),
    # Release 2 L22: a SHOP PRODUCT's or VARIANT's own `archived_at` (a retired catalogue row kept
    # for past orders); the shop views and the public catalogue resolve a servable space first.
    ("shop/pricing.py", "resolve_items"),
    ("shop/public.py", "_variants"),
    ("shop/public.py", "public_products"),
    ("shop/services_catalogue.py", "_components"),
    ("shop/services_catalogue.py", "archive_product"),
    ("shop/services_catalogue.py", "archive_variant"),
    ("shop/views_staff_catalogue.py", "ShopProductListView.get"),
    # 0.12.0: a CARD DESIGN's, ID PROGRAMME's, DAY-PASS PRODUCT's or SHOP VARIANT's own `archived_at` (a retired
    # catalogue row kept for issued cards, passes and past orders), never the makerspace's; each caller resolves
    # a servable space first.
    ("card_designs/archive.py", "archive"),
    ("card_designs/archive.py", "unarchive"),
    ("card_designs/resolution.py", "get_or_create"),
    ("card_designs/resolution.py", "resolve"),
    ("card_designs/views_designs.py", "SpaceCardDesignListView.get"),
    ("events/id_cards.py", "has_published_design"),
    ("events/id_cards.py", "reconcile_due"),
    ("id_programmes/services.py", "archive"),
    ("id_programmes/services.py", "unarchive"),
    ("id_programmes/services.py", "update"),
    ("id_programmes/views.py", "OrganizationProgrammeListView.get"),
    ("makerspaces/guest_pass_day.py", "archive_product"),
    ("makerspaces/guest_pass_day.py", "public_products"),
    ("makerspaces/guest_pass_day.py", "save_product"),
    ("makerspaces/guest_pass_day.py", "sell_day_pass"),
    ("operations/reports_shop_products.py", "build_shop_stock_value"),
    ("shop/event_offers.py", "_variants"),
    # 0.12.0 (member units, title cards, public offers): a MEMBER UNIT's, CARD DESIGN's, MEMBERSHIP TITLE's,
    # MEMBERSHIP PLAN's or SHOP PRODUCT's own `archived_at` (a retired row kept for its history), never the
    # makerspace's; each caller already resolves a servable space (the unit services run under the member-unit
    # module gate, the quota counters under a loaded space, the public offers over the servable public list).
    ("admin_api/bulk_import_members_units.py", "resolve_import_unit"),
    ("card_designs/resolution_roles.py", "get_or_create_variant"),
    ("card_designs/resolution_roles.py", "resolve_event_card"),
    ("card_designs/resolution_roles.py", "variant"),
    ("card_designs/title_cards.py", "status_of"),
    ("card_designs/title_cards.py", "title_rows"),
    ("card_designs/views_badges.py", "_event_designs"),
    ("inventory/public_offers.py", "build_public_offers"),
    ("makerspaces/member_unit_assign.py", "_live_unit"),
    ("makerspaces/member_unit_assign.py", "set_plan_units"),
    ("makerspaces/member_units.py", "archive_unit"),
    ("makerspaces/member_units.py", "create_unit"),
    ("makerspaces/member_units.py", "move_unit"),
    ("makerspaces/member_units.py", "restore_unit"),
    ("makerspaces/member_units.py", "tree"),
    ("makerspaces/membership_join_units.py", "_existing_unit"),
    ("makerspaces/membership_join_units.py", "_invite_unit"),
    ("makerspaces/membership_join_units.py", "apply_request_unit"),
    ("makerspaces/membership_join_units.py", "unit_by_code"),
    ("managed_hosting/extra_quota_counters.py", "member_units"),
    ("managed_hosting/extra_quota_counters.py", "membership_plans"),
    ("managed_hosting/extra_quota_counters.py", "shop_products"),
    ("operations/reports_unit_league.py", "_tallies"),
}


@dataclass(frozen=True, order=True)
class Site:
    path: str
    function: str
    line: int


def _call_name(node):
    return getattr(node.func, "attr", None) or getattr(node.func, "id", None)


def _archive_style(node, parents):
    if isinstance(node, ast.keyword):
        parent = parents.get(node)
        return bool(
            node.arg
            and "archived_at" in node.arg
            and isinstance(parent, ast.Call)
            and _call_name(parent)
            in {"exclude", "filter", "get", "get_object_or_404", "update"}
        )
    if isinstance(node, ast.Attribute):
        return node.attr == "archived_at"
    return isinstance(node, ast.Call) and _call_name(node) in ARCHIVE_HELPERS


def _function_name(node, parents):
    names = []
    current = node
    while True:
        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.append(current.name)
        if current not in parents:
            break
        current = parents[current]
    return ".".join(reversed(names)) or "<module>"


def _sites():
    sites = []
    functions = {}
    for path in APPS_DIR.rglob("*.py"):
        if "migrations" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        parents = {
            child: parent
            for parent in ast.walk(tree)
            for child in ast.iter_child_nodes(parent)
        }
        relative = path.relative_to(APPS_DIR).as_posix()
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                functions[(relative, _function_name(node, parents))] = node
            if _archive_style(node, parents):
                sites.append(
                    Site(relative, _function_name(node, parents), node.lineno)
                )
    return sites, functions


def _consults_servability(function):
    return any(
        isinstance(node, ast.Call) and _call_name(node) in SERVABILITY_CALLS
        for node in ast.walk(function)
    )


def test_every_archived_style_site_participates_in_tenant_servability():
    sites, functions = _sites()
    uncovered = {
        (site.path, site.function)
        for site in sites
        if (site.path, site.function) not in EXEMPTIONS
        and not _consults_servability(functions[(site.path, site.function)])
    }
    assert not uncovered, (
        "Archived-style tenant exclusions must call the canonical servability policy "
        f"or be documented as recovery/import exemptions: {sorted(uncovered)}"
    )

    discovered_exemptions = {
        (site.path, site.function)
        for site in sites
        if (site.path, site.function) in EXEMPTIONS
    }
    assert discovered_exemptions == EXEMPTIONS, (
        "Stale tenant-servability exemptions must be removed: "
        f"{sorted(EXEMPTIONS - discovered_exemptions)}"
    )


def test_legacy_archived_helpers_delegate_to_unservable_policy():
    _, functions = _sites()
    helper = functions[("accounts/rbac.py", "archived_makerspace_ids")]
    assert any(
        isinstance(node, ast.Call) and _call_name(node) == "unservable_makerspace_ids"
        for node in ast.walk(helper)
    )
    subtractor = functions[("accounts/rbac.py", "_exclude_archived_ids")]
    assert any(
        isinstance(node, ast.Call) and _call_name(node) == "archived_makerspace_ids"
        for node in ast.walk(subtractor)
    )
