"""Repairs and warranties grouped by area (decision 241).

Repairs come from `repairs.authority.visible_issues` (the manager's areas and machine
scope, plus a Technician's own assigned jobs), so a Technician sees their jobs grouped by
machine type then machine and nothing else. Warranties come from the warranty report's own
host querysets (inventory assets with EDIT_INVENTORY, machines through the manageable
machine scope). Issue rows carry the title and state only, never the reporter.
"""

from rest_framework.exceptions import NotFound, PermissionDenied

from apps.operations.area_overview_upkeep import area_step, category_step, machine_step, type_step
from apps.operations.area_tree import GroupTree, money_text, none_key

REPAIR_AREA = {"machines": "machines", "inventory": "inventory", "rooms": "bookings"}


def _issue_path(issue):
    area = REPAIR_AREA[issue.area]
    if issue.area == "machines":
        machine = issue.machine
        return [area_step(area), type_step(getattr(machine, "machine_type_id", None),
                                           getattr(getattr(machine, "machine_type", None), "name", "")),
                machine_step(getattr(machine, "pk", None), getattr(machine, "name", ""))]
    if issue.area == "inventory":
        product = issue.product or getattr(issue.asset, "product", None)
        category = getattr(product, "category", None)
        return [area_step(area), category_step(getattr(category, "pk", None), getattr(category, "name", ""))]
    room = issue.room
    return [area_step(area), ("room", f"room:{room.pk}" if room else none_key("room"), getattr(room, "name", ""))]


def repairs_tree(actor, space, *, areas=None, status="open"):
    from apps.separability.registry import runtime_active
    if not runtime_active("maintenance"):
        raise NotFound()
    from apps.maintenance.models import IssueReport
    from apps.maintenance.repairs import authority
    from apps.maintenance.repairs.views_common import require_issues

    require_issues(space)
    visible = authority.visible_issues(actor, space)
    rows = IssueReport.objects.filter(pk__in=visible.values("pk")).select_related(
        "machine__machine_type", "product__category", "asset__product__category", "room")
    if status == "open":
        rows = rows.filter(state__in=IssueReport.OPEN_STATES)
    elif status != "all":
        rows = rows.filter(state=status)
    tree = GroupTree()
    for issue in rows.order_by("-created_at", "-pk"):
        if areas and REPAIR_AREA[issue.area] not in areas:
            continue
        quoted = issue.quote_amount is not None and issue.quote_currency
        tree.add(_issue_path(issue), attention=int(issue.state in IssueReport.OPEN_STATES),
                 money={issue.quote_currency.lower(): issue.quote_amount} if quoted else None,
                 item={"id": issue.pk, "label": issue.title, "status": issue.state, "priority": issue.priority,
                       "amount": money_text(issue.quote_amount) if quoted else None,
                       "currency": issue.quote_currency.lower() if quoted else ""})
    return tree


def warranties_tree(actor, space, *, areas=None, status=None):
    from apps.separability.registry import runtime_active
    if not runtime_active("warranty"):
        raise NotFound()
    from django.utils import timezone

    from apps.accounts import rbac
    from apps.machines import access as machine_access
    from apps.makerspaces.folded_capabilities import WARRANTY_KEYS, require_any_capability
    from apps.warranty.views_report import _asset_hosts, _host_warranty, _machine_hosts
    from apps.warranty.status import STATUS_EXPIRED, STATUS_EXPIRING_SOON, warranty_status

    require_any_capability(space, WARRANTY_KEYS)
    if not (rbac.can(actor, rbac.Action.EDIT_INVENTORY, space.pk)
            or machine_access.can_see_machines(actor, space.pk)):
        raise PermissionDenied()
    today = timezone.localdate()
    filters = {"status": status} if status else {}
    tree = GroupTree()

    def add(path, host_kind, host_id, label, warranty):
        state = warranty_status(warranty, today) if warranty is not None else "unknown"
        tree.add(path, attention=int(state in (STATUS_EXPIRED, STATUS_EXPIRING_SOON)), item={
            "id": host_id, "label": label, "status": state, "source": host_kind,
            "expires_on": getattr(warranty, "warranty_expires_on", None)})

    if not areas or "inventory" in areas:
        for asset in _asset_hosts(actor, space, today, filters).select_related("product__category"):
            category = getattr(asset.product, "category", None)
            add([area_step("inventory"), category_step(getattr(category, "pk", None), getattr(category, "name", ""))],
                "asset", asset.pk, asset.asset_tag, _host_warranty(asset))
    if not areas or "machines" in areas:
        for machine in _machine_hosts(actor, space, today, filters):
            add([area_step("machines"), type_step(machine.machine_type_id, getattr(machine.machine_type, "name", ""))],
                "machine", machine.pk, machine.name, _host_warranty(machine))
    return tree
