"""`quote()`: the ONE price resolver every chargeable seam and every preview calls (lane L15).

    quote(makerspace, domain, target=None, member=None, params=None) -> Quote

Pattern, the same for every domain: rate card -> item override -> loan waiver -> the
member's best automatic discount -> a frozen `Quote`. The preview and the charge call
this same function, so the price a member is shown is the price they are charged (A8).

Targets and params by domain:

* `loans` -- target: a `HardwareRequest` (or None with `params["items"]`, a list of
  `(InventoryProduct, quantity)`). params: `components` (any of `rental`, `deposit`,
  `late`; default all), `days` (rental days), `due_at` / `now` (late fee).
* `machines` -- target: a `MachineServiceRequest`, or None with `params` `machine`,
  `machine_type`, `pool`, `minutes`, `quantity`; plus `outcome` (`completed`|`failed`)
  and `failure_charge` (`none`|`material_only`|`full`, default the space's choice).
* `bookings` -- target: a `BookableSpace`; params `starts_at`, `ends_at`.
* `events` -- target: an `Event`; params `ticket` (an `EventTicketType`).
* `membership` -- target: a `MembershipPlan` or None; params `joining`.

`member` decides the automatic discount (None: no discount). A total of 0 means the
caller raises NO `Payment` and audits `charge.free_by_pricing`.
"""

from dataclasses import replace

from apps.payments.pricing import build_loans, build_machines, build_other
from apps.payments.pricing.components import domain_known
from apps.payments.pricing.discounts import best_discount
from apps.payments.pricing.errors import PricingDomainUnknown
from apps.payments.pricing.quotes import Quote
from apps.payments.pricing.rates import RateCard
from apps.payments.pricing.waivers import apply_waivers


def rate_card(makerspace, domain):
    if not domain_known(domain):
        raise PricingDomainUnknown(domain)
    return RateCard(makerspace, domain)


def quote(makerspace, domain, target=None, member=None, params=None, *, discounts=True, card=None):
    params = dict(params or {})
    card = card or rate_card(makerspace, domain)
    lines, notes = _build(card, domain, target, params)
    result = Quote(domain=domain, currency=card.currency, lines=tuple(lines), mode=card.mode, notes=tuple(notes))
    if domain == "loans" and target is not None and getattr(target, "pk", None):
        result = apply_waivers(result, target)
    if discounts and member is not None:
        result = best_discount(makerspace, domain, member, result)
    return result


def _build(card, domain, target, params):
    if domain == "loans":
        return _loans(card, target, params), ()
    if domain == "machines":
        return _machines(card, target, params)
    if domain == "bookings":
        return build_other.booking_lines(card, target, starts_at=params.get("starts_at"),
                                         ends_at=params.get("ends_at")), ()
    if domain == "events":
        return build_other.event_lines(card, target, ticket=params.get("ticket")), ()
    return build_other.membership_lines(card, target, joining=bool(params.get("joining"))), ()


def _loans(card, request, params):
    wanted = set(params.get("components") or ("rental", "deposit", "late"))
    items = params.get("items")
    lines = []
    if "rental" in wanted:
        rental_items = items if items is not None else build_loans.items_of(request)
        lines += build_loans.rental_lines(card, rental_items, int(params.get("days") or 0))
    if "deposit" in wanted:
        deposit_items = items if items is not None else build_loans.items_of(request, accepted=True)
        lines += build_loans.deposit_lines(card, deposit_items)
    if "late" in wanted:
        late_items = items if items is not None else build_loans.items_of(request)
        due_at = params.get("due_at", getattr(request, "return_due_at", None))
        lines += build_loans.late_lines(card, late_items, due_at=due_at, now=params.get("now"))
    return lines


def _machines(card, service_request, params):
    if service_request is not None:
        machine = service_request.assigned_machine
        params.setdefault("machine", machine)
        params.setdefault("pool", service_request.run_consumable_pool)
        params.setdefault("minutes", service_request.actual_minutes)
        params.setdefault("quantity", build_machines.service_request_quantity(service_request))
    return build_machines.lines(
        card, machine=params.get("machine"), machine_type=params.get("machine_type"), pool=params.get("pool"),
        minutes=params.get("minutes") or 0, quantity=params.get("quantity") or 0,
        outcome=params.get("outcome", "completed"), failure_charge=params.get("failure_charge"),
    )


def with_promo(result, promo, saving):
    """Record an event promo code applied on top of the automatic discount (A3)."""
    return replace(result, promo={"id": promo.pk, "code": getattr(promo, "code", ""), "saving": str(saving)})
