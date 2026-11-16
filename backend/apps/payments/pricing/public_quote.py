"""The member-facing price preview (`POST pricing/quote`, lane L15, A6/A8).

Anyone may ask (anonymous allowed, throttled) for things the space shows publicly: a
public catalogue item, a public room, a public machine (or a type one of them has), a
public event, an active plan. A signed-in member of the space also gets their own price
(best automatic discount) and, for their OWN loan request, any waiver. It never returns
hidden counts, storage, box, QR or requester data -- only prices.

The response carries the net quote (the price the charge will be raised at), its digest
(send it back on submit: 409 `price_changed` if it moved), the tax split from L5's live
policy, "members pay X" for a non-member, the refundable deposit, and the late /
damage / lost policy.
"""

from django.http import Http404

from apps.makerspaces.platform import module_enabled
from apps.payments.pricing import resolver
from apps.payments.pricing.components import DOMAIN_MODULES
from apps.payments.pricing.discounts import member_plan_ids, members_price


def _get(queryset, pk):
    row = queryset.filter(pk=pk).first() if pk else None
    if row is None:
        raise Http404
    return row


def _loans(space, viewer, data):
    from apps.accounts.rbac_catalogue import scope_public_catalogue
    from apps.hardware_requests.models import HardwareRequest
    from apps.inventory.models import InventoryProduct

    if data.get("request_id"):
        if viewer is None:
            raise Http404
        request = _get(HardwareRequest.objects.filter(makerspace=space, requester=viewer), data["request_id"])
        return request, {"days": data.get("days") or 0}
    products = scope_public_catalogue(InventoryProduct.objects.filter(is_public=True, is_archived=False), space)
    items = [(_get(products, row["product_id"]), row["quantity"]) for row in data.get("items") or ()]
    return None, {"items": items, "days": data.get("days") or 0, "components": ("rental", "deposit")}


def _machines(space, data):
    from apps.machines.models import Machine, MachineConsumablePool

    machines = Machine.objects.filter(makerspace=space, is_public=True, is_active=True).select_related("machine_type")
    params = {"minutes": data.get("minutes") or 0, "quantity": data.get("quantity") or 0}
    if data.get("machine_id"):
        params["machine"] = _get(machines, data["machine_id"])
    elif data.get("machine_type_id"):
        # A type is quotable only when the space shows at least one public machine of it.
        machine = machines.filter(machine_type_id=data["machine_type_id"]).first()
        if machine is None:
            raise Http404
        params["machine_type"] = machine.machine_type
    else:
        raise Http404
    if data.get("pool_id"):
        params["pool"] = _get(MachineConsumablePool.objects.filter(makerspace=space, is_active=True), data["pool_id"])
    return None, params


def _target(space, domain, viewer, data):
    if domain == "loans":
        return _loans(space, viewer, data)
    if domain == "machines":
        return _machines(space, data)
    if domain == "bookings":
        from apps.bookings.models import BookableSpace
        rooms = BookableSpace.objects.filter(makerspace=space, is_public=True, is_active=True)
        if data.get("space_token"):
            rooms = rooms.filter(public_token=data["space_token"])
            room = rooms.first() or _get(rooms, None)
        else:
            room = _get(rooms, data.get("space_id"))
        return room, {"starts_at": data.get("starts_at"), "ends_at": data.get("ends_at")}
    if domain == "events":
        from apps.events.models import EventTicketType
        from apps.events.website_visibility import public_events
        events = public_events(space)
        if data.get("event_token"):
            events = events.filter(public_token=data["event_token"])
            event = events.first() or _get(events, None)
        else:
            event = _get(events, data.get("event_id"))
        ticket = _get(EventTicketType.objects.filter(event=event), data["ticket_type_id"]) \
            if data.get("ticket_type_id") else None
        return event, {"ticket": ticket}
    from apps.makerspaces.models import MembershipPlan
    plan = _get(MembershipPlan.objects.filter(makerspace=space, is_active=True), data["plan_id"]) \
        if data.get("plan_id") else None
    return plan, {"joining": bool(data.get("joining"))}


def _member(space, viewer):
    if viewer is None or not getattr(viewer, "is_authenticated", False):
        return None
    return viewer if member_plan_ids(space, viewer) is not None else None


def _policy(card, domain):
    if domain != "loans":
        return None
    late = card.default("late_per_day")
    damage, lost = card.default("damage"), card.default("lost")
    return {"late_per_day": late.amount, "late_cap": late.cap, "grace_days": late.grace,
            "damage_default": damage.amount, "lost_default": lost.amount,
            "damage_lost_text": "Staff set damage and lost charges at return, only with a return photo."}


def _refund_summary(space, domain):
    from apps.payments.models import RefundPolicy

    if domain not in ("events", "bookings"):
        return None
    policy = RefundPolicy.objects.filter(makerspace=space, area=domain, plan__isnull=True).first()
    if policy is None:
        return "Refunds are decided by staff on request."
    hours = policy.full_before_minutes // 60
    return f"Full refund if you cancel at least {hours} hours before the start." if hours else \
        "Refunds are decided by staff under the space's policy."


def public_quote(space, domain, viewer, data):
    from apps.payments.pricing.serializers import quote_payload
    from apps.payments.tax.engine import estimate

    if not module_enabled(space, DOMAIN_MODULES.get(domain, "")):
        raise Http404
    from apps.payments.availability import charge_tracking_enabled
    from apps.payments.pricing.errors import ChargesOff

    if not charge_tracking_enabled(space, domain):
        # #184 G2: a free domain has no price to preview -- not even "members pay X".
        raise ChargesOff(domain)
    card = resolver.rate_card(space, domain)
    target, params = _target(space, domain, viewer, data)
    member = _member(space, viewer)
    priced = resolver.quote(space, domain, target, member=member, params=params, card=card)
    charged = priced.subset(*{line.subject_type for line in priced.lines if line.subject_type != "loan_deposit"})
    deposit = priced.subset("loan_deposit") if domain == "loans" else None
    tax = estimate(space, charged.total, charged.currency, member=member)
    members = None
    if member is None and charged.lines:
        hint = members_price(space, domain, charged)
        members = hint.total if hint is not None else None
    return {
        "quote": quote_payload(charged), "digest": charged.digest,
        "tax": {"net": tax.net, "tax": tax.tax, "gross": tax.gross, "inclusive": tax.inclusive, "mode": tax.mode},
        "members_total": members, "member_price_applied": bool(charged.discount),
        "deposit": {"amount": deposit.total, "refundable": True} if deposit and deposit.total > 0 else None,
        "policy": _policy(card, domain), "refund_summary": _refund_summary(space, domain),
    }
