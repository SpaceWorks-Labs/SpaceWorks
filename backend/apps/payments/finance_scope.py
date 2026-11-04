"""Who sees and records which finance rows (#100), resolved once per request through rbac.

Space Managers and finance staff (`view_finance`) see every row. Each area's manager sees
that area's money, in and out, and nothing else:

* Inventory Manager (`edit_inventory`) -- inventory and lending (rental, deposit, late,
  damage and lost fees, To-Buy purchases, inventory repairs);
* Booking Manager (`manage_bookings`) -- booking charges, room repairs and maintenance;
* Machine Manager (`manage_machines`) -- machine charges, consumables, repairs and
  maintenance, limited to the machine types their role covers (`machines.role_scope`);
* Event Manager (`manage_events`) -- events money: registrations, tickets, reimbursement
  and prize payouts (#128 C-16).

Recording spending follows the same areas (#94). Finance staff holding BOTH
`view_finance` and `record_payment` record in every area; `view_finance` alone is
read-only, and `record_payment` alone (the counter's cash receipts) records no spending.
"""

from dataclasses import dataclass

from django.db.models import Q

from apps.accounts import rbac

DOMAIN_ACTIONS = {
    "inventory": rbac.Action.EDIT_INVENTORY,
    "loans": rbac.Action.EDIT_INVENTORY,
    "machines": rbac.Action.MANAGE_MACHINES,
    "bookings": rbac.Action.MANAGE_BOOKINGS,
    "events": rbac.Action.MANAGE_EVENTS,
}
#: Payment subject types per finance domain (the ledger's own vocabulary).
PAYMENT_DOMAINS = {
    "machine_service_request": "machines",
    "booking": "bookings",
    "event_registration": "events",
    "makerspace_membership": "membership",
    "membership_term": "membership",
    "membership_request": "membership",
    "loan_deposit": "loans",
    "loan_late_fee": "loans",
    "loan_rental": "loans",
    "loan_damage": "loans",
    "loan_lost": "loans",
    "machine_session": "machines",
    # Lane L6: ticket orders and venue fees are events income.
    "event_order": "events",
    "event_venue_fee": "events",
}


@dataclass(frozen=True)
class FinanceView:
    """What one actor may see in one space. `everything` short-circuits the rest."""

    everything: bool = False
    domains: frozenset = frozenset()
    #: None = every machine type; otherwise the type ids a scoped Machine Manager covers.
    machine_types: frozenset | None = None
    record_domains: frozenset = frozenset()
    record_everything: bool = False

    @property
    def any(self):
        return self.everything or bool(self.domains)

    def sees(self, domain, machine_type_id=None):
        if self.everything:
            return True
        if domain not in self.domains:
            return False
        if domain == "machines" and self.machine_types is not None:
            return machine_type_id in self.machine_types
        return True

    def may_record(self, domain, machine_type_id=None):
        if self.record_everything:
            return True
        if domain not in self.record_domains:
            return False
        if domain == "machines" and self.machine_types is not None:
            return machine_type_id in self.machine_types
        return True


def finance_view(actor, makerspace_id):
    """Resolve the actor's finance view for one makerspace (a handful of rbac lookups)."""
    if rbac.can(actor, rbac.Action.VIEW_FINANCE, makerspace_id):
        record = rbac.can(actor, rbac.Action.RECORD_PAYMENT, makerspace_id)
        return FinanceView(everything=True, record_everything=record)
    domains = frozenset(domain for domain, action in DOMAIN_ACTIONS.items() if rbac.can(actor, action, makerspace_id))
    machine_types = None
    if "machines" in domains:
        from apps.machines.role_scope import EXEMPT, manage_scope_for

        scope = manage_scope_for(actor, makerspace_id)
        if scope is not EXEMPT:
            machine_types = frozenset(scope[0])
    return FinanceView(domains=domains, machine_types=machine_types, record_domains=domains)


def entry_q(view):
    """A Q over `LedgerEntry` for the rows this view sees."""
    if view.everything:
        return Q()
    q = Q(pk__in=[])
    for domain in view.domains:
        if domain == "machines" and view.machine_types is not None:
            q |= Q(domain="machines", machine_type_id__in=view.machine_types)
        else:
            q |= Q(domain=domain)
    return q


def payment_domain(payment):
    return PAYMENT_DOMAINS.get(payment.subject_type, "general")
