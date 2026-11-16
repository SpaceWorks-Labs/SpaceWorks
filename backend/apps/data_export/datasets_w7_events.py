"""EventStaffGrant and EventStaffGrantInvite deliberately have no export dataset.
Their entire credential/authority rows are classified OmittedModel at both fidelities.
"""
from .types import TenantPredicate

EVENT_DATASET_SPECS = {
    "events.EventInvite": ("events/invites.csv", TenantPredicate(("makerspace",))),
    "events.EventPromoCode": ("events/promo_codes.csv", TenantPredicate(("makerspace",))),
    "events.EventTicketType": ("events/ticket_types.csv", TenantPredicate(("makerspace",))),
    "events.EventCategory": ("events/categories.csv", TenantPredicate(("makerspace",))),
}
