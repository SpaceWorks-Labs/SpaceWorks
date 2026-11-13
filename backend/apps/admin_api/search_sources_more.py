"""Decision 242 (U6): the extra staff search sources, each behind its own action and module check.

Jobs, shop orders, payments (by receipt number or reference), incidents and guest passes. The existing
`search.search_hits` keeps its six sources; this adds the rest with the same rules: rbac-scoped querysets,
a module or capability switch, matching only unencrypted columns (ids, usernames, titles, receipt numbers),
and counts bounded by `limit`. A role without the action contributes no hits for that source.
"""

from apps.accounts import rbac
from apps.makerspaces.platform import feature_enabled, module_enabled

ENTITIES = ("jobs", "shop", "payments", "incidents", "passes")


def _digits(term):
    return int(term) if term.isdecimal() and len(term) <= 18 else None


def extra_hits(actor, space, term, limit):
    hits = []

    def add(entity, rows, label, tab, query):
        for row in rows.order_by("pk")[:limit]:
            hits.append({"entity": entity, "id": row.pk, "label": label(row), "tab": tab, "query": query(row)})

    number = _digits(term)
    if module_enabled(space, "machines") and module_enabled(space, "machine_service") and rbac.can(
            actor, rbac.Action.MANAGE_MACHINES, space.pk):
        from apps.machines import role_scope
        from apps.machines.models import MachineServiceRequest
        jobs = role_scope.scoped_service_requests(
            actor, rbac.scope_by_makerspace(actor, MachineServiceRequest.objects.filter(makerspace=space)), [space.pk])
        if number is not None:
            add("jobs", jobs.filter(pk=number), lambda row: f"Job #{row.pk}", "machines", lambda row: {"job": str(row.pk)})

    if module_enabled(space, "shop") and rbac.can(actor, rbac.Action.MANAGE_SHOP, space.pk):
        from apps.shop.models import ShopOrder
        from django.db.models import Q
        orders = rbac.scope_by_action(actor, rbac.Action.MANAGE_SHOP, ShopOrder.objects.filter(makerspace=space),
                                      field="makerspace_id")
        match = Q(pickup_code__iexact=term)
        if number is not None:
            match |= Q(pk=number)
        add("shop", orders.filter(match), lambda row: f"Order #{row.pk}", "shop", lambda row: {"order": str(row.pk)})

    from apps.payments import area_queue
    if area_queue.owned_subject_types(actor, space.pk) != []:
        from django.db.models import Q
        from apps.payments.models import ManualSettlement, PaymentDocument
        mine = area_queue.area_payments(actor, space.pk)
        found = mine.filter(
            Q(pk__in=PaymentDocument.objects.filter(makerspace=space, number__iexact=term).values("payment_id"))
            | Q(pk__in=ManualSettlement.objects.filter(payment__makerspace=space, reference__iexact=term
                                                       ).values("payment_id"))
            | (Q(pk=number) if number is not None else Q(pk__in=[])))
        add("payments", found, lambda row: f"Payment #{row.pk}", "payments", lambda row: {"payment": str(row.pk)})

    from apps.maintenance.incidents import scope as incident_scope
    if incident_scope.incidents_on(space) and incident_scope.can_record(actor, space):
        rows = incident_scope.visible_incidents(actor, space).filter(title__icontains=term)
        add("incidents", rows, lambda row: row.title, "incidents", lambda row: {"id": str(row.pk)})

    if feature_enabled(space, "membership.guest_passes") and rbac.can(actor, rbac.Action.MANAGE_MEMBERS, space.pk):
        from apps.makerspaces.models import GuestPass
        passes = rbac.scope_by_action(actor, rbac.Action.MANAGE_MEMBERS, GuestPass.objects.filter(
            makerspace=space, holder__username__icontains=term).select_related("holder"), field="makerspace_id")
        add("passes", passes, lambda row: f"Guest pass · {row.holder.username}", "members", lambda row: {"section": "guests", "pass": str(row.pk)})
    return hits
