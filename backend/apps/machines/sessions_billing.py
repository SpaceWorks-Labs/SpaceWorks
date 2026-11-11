"""Session billing on the L15 rate card (#158.4): an hourly rate frozen at START.

At start the machine's `time` component is quoted through `pricing.quote()` (machine
override, the type's price row, the space default, with the billing increment and
minimum) for one hour, the member's best automatic discount is applied, and the snapshot
and digest are frozen on the session. At stop the charge is rebuilt from that snapshot
alone -- the frozen rate, increment, minimum and discount -- so a later price change
never touches a session already running, and a price RISE never charges anyone more.

A session bills only while machine charges are tracked (`charges.enabled` +
`charges.machines`). A device session that runs an L12 job is billed through the job
only. The charge is a PENDING `Payment` in the ledger; staff settle or waive it through
the usual L5 path. Money never moves here.
"""

import logging
from dataclasses import replace
from decimal import Decimal
from types import SimpleNamespace

from django.db import IntegrityError, transaction

from apps.audit import services as audit

logger = logging.getLogger(__name__)
TIME = "time"
DOMAIN = "machines"


def billing_active(makerspace):
    from apps.payments.availability import charge_tracking_enabled
    return charge_tracking_enabled(makerspace, DOMAIN)


def start_quote(machine, member):
    """The member's frozen hourly rate for `machine` (a `Quote` with at most one time line)."""
    from apps.payments.pricing import best_discount, quote
    base = quote(machine.makerspace, DOMAIN, None, member=None, params={"machine": machine, "minutes": 60})
    hourly = replace(base, lines=tuple(line for line in base.lines if line.component == TIME), notes=())
    if member is None or not hourly.lines:
        return hourly
    return best_discount(machine.makerspace, DOMAIN, member, hourly)


def rate_terms(snapshot):
    """`{unit_amount, increment, minimum, currency}` of a frozen snapshot, or None when free."""
    time_line = next((row for row in (snapshot or {}).get("lines") or () if row.get("component") == TIME), None)
    if time_line is None or Decimal(time_line.get("unit_amount") or "0") <= 0:
        return None
    detail = time_line.get("detail") or {}
    return {"unit_amount": time_line["unit_amount"], "increment": int(detail.get("increment") or 0),
            "minimum": int(detail.get("minimum") or 0), "currency": snapshot.get("currency", ""),
            "source": time_line.get("source", ""), "target": time_line.get("target")}


def _frozen_rule(discount):
    # A discount recorded at start applied to the time line, so it applies to it again.
    return SimpleNamespace(pk=discount.get("id"), name=discount.get("name", ""), audience=discount.get("audience", ""),
                           percent_bps=int(discount.get("percent_bps") or 0),
                           amount_off=Decimal(discount.get("amount_off") or "0"), components=(TIME,))


def final_quote(snapshot, minutes):
    """The charge for `minutes` at the frozen rate, increment, minimum and discount."""
    from apps.payments.pricing.build_machines import billed_minutes
    from apps.payments.pricing.components import component
    from apps.payments.pricing.discounts import apply, savings
    from apps.payments.pricing.quotes import Quote, line
    from apps.payments.pricing.rates import Rate
    terms = rate_terms(snapshot)
    currency = (snapshot or {}).get("currency", "")
    if terms is None:
        return Quote(domain=DOMAIN, currency=currency)
    rate = Rate(amount=Decimal(terms["unit_amount"]), increment=terms["increment"], minimum=terms["minimum"])
    billed = billed_minutes(minutes, rate)
    if billed <= 0:
        return Quote(domain=DOMAIN, currency=currency, mode=snapshot.get("mode", "paid"))
    lines = (line(component(DOMAIN, TIME), currency=currency, quantity=Decimal(billed) / Decimal(60),
                  unit_amount=rate.amount, rate_source=terms["source"], target=terms["target"],
                  detail={"minutes": int(minutes), "billed_minutes": billed, "increment": terms["increment"],
                          "minimum": terms["minimum"]}),)
    result = Quote(domain=DOMAIN, currency=currency, lines=lines, mode=snapshot.get("mode", "paid"))
    if snapshot.get("discount"):
        rule = _frozen_rule(snapshot["discount"])
        result = apply(result, rule, savings(rule, DOMAIN, result.lines, currency))
    return result


def payment_for(session):
    from apps.payments.models import Payment
    return Payment.objects.filter(makerspace_id=session.makerspace_id, subject_type=Payment.SubjectType.MACHINE_SESSION,
                                  subject_id=session.pk).first()


def raise_charge(session, *, minutes, member, actor):
    """Raise the session's PENDING charge once; None when nothing is owed. Never raises."""
    from apps.payments.models import Payment
    from apps.payments.pricing.charging import raise_priced
    from apps.payments.pricing.quotes import FrozenQuote
    from apps.payments.services import create_payment
    if not session.billable or session.service_request_id or member is None:
        return None
    try:
        with transaction.atomic():
            if not billing_active(session.makerspace):
                return None
            existing = payment_for(session)
            if existing is not None:
                return existing
            priced = final_quote(session.quote_snapshot, minutes)
            frozen = FrozenQuote(priced.to_snapshot(session={
                "session_id": session.pk, "minutes": int(minutes), "start_digest": session.quote_digest}))
            payment = raise_priced(
                frozen, makerspace=session.makerspace, subject_type=Payment.SubjectType.MACHINE_SESSION,
                subject_id=session.pk, member=member, created_by=actor or member, target=session,
                subject_label=f"{session.machine.name} session", create=create_payment)
            if payment is not None:
                audit.record(actor, "machine_session.charge_raised", makerspace=session.makerspace, target=session,
                             meta={"session_id": session.pk, "machine_id": session.machine_id, "payment_id": payment.pk,
                                   "amount": str(payment.amount),
                                   "currency": payment.currency, "minutes": int(minutes)})
            return payment
    except IntegrityError:
        # A concurrent stop raised the one charge first (payment_one_per_subject).
        return payment_for(session)
    except Exception:
        # The stop must not fail on a charge error, but a debt that silently vanishes is
        # lost money: always leave a trace.
        logger.exception("machine_session_charge_not_recorded", extra={"session_id": session.pk})
        return None
