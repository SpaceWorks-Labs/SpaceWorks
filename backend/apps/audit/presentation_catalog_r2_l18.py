"""Audit presentation for lane L18: donations, pledges, sponsors and personal calendar links.

Metadata is ids, amounts, statuses and switches only. A donor's or sponsor contact's name,
email, address, note and PAN are never in an audit row; neither is a feed token.
"""

from .presentation_catalog_types import P

_GIFT = ("donation_id", "payment_id", "amount", "currency", "source", "campaign_id", "pledge_id", "guest",
         "tax_receipt_requested")
_PLEDGE = ("pledge_id", "status")

ENTRIES = (
    P("donation.created", "Donation recorded", _GIFT),
    P("donation.paid", "Donation received", ("donation_id", "status", "tax_receipt")),
    P("donation.cancelled", "Donation cancelled", ("donation_id", "status", "reason_given")),
    P("donation.return_case_opened", "Refund case opened to return a gift", ("case_id", "payment_id", "subject_type")),
    P("donation.campaign_created", "Donation campaign created", ("campaign_id", "kind")),
    P("donation.campaign_updated", "Donation campaign changed", ("campaign_id", "fields")),
    P("pledge.created", "Donation pledge made", ("pledge_id", "amount", "currency", "interval", "guest", "campaign_id")),
    P("pledge.paused", "Donation pledge paused", _PLEDGE),
    P("pledge.resumed", "Donation pledge resumed", _PLEDGE),
    P("pledge.updated", "Donation pledge changed", _PLEDGE),
    P("pledge.cancelled", "Donation pledge cancelled", _PLEDGE),
    P("pledge.period_raised", "Pledge period charge raised", ("pledge_id", "donation_id", "period_start")),
    P("sponsor.created", "Sponsor added", ("sponsor_id", "fields")),
    P("sponsor.updated", "Sponsor changed", ("sponsor_id", "fields")),
    P("sponsor.archived", "Sponsor archived", ("sponsor_id",)),
    P("sponsor.restored", "Sponsor restored", ("sponsor_id",)),
    P("sponsor.tier_created", "Sponsor tier created", ("tier_id",)),
    P("sponsor.tier_updated", "Sponsor tier changed", ("tier_id", "fields")),
    P("sponsor.charge_raised", "Sponsorship payment recorded as owed", ("sponsor_id", "charge_id", "payment_id",
                                                                        "amount")),
    P("sponsor.charge_paid", "Sponsorship payment received", ("sponsor_id", "charge_id", "payment_id", "status")),
    P("sponsor.event_linked", "Sponsor linked to an event", ("sponsor_id", "event_sponsor_id", "event_id")),
    P("sponsor.event_unlinked", "Sponsor unlinked from an event", ("sponsor_id", "event_sponsor_id")),
    P("sponsor.logo_updated", "Sponsor logo changed", ("sponsor_id",)),
    P("sponsor.logo_removed", "Sponsor logo removed", ("sponsor_id",)),
    P("perk.copied", "Tier perks copied to a sponsor", ("sponsor_id", "tier_id", "count")),
    P("perk.created", "Sponsor perk added", ("perk_id", "sponsor_id", "tier_id")),
    P("perk.updated", "Sponsor perk changed", ("perk_id", "sponsor_id", "tier_id")),
    P("perk.fulfilled", "Sponsor perk fulfilled", ("perk_id", "sponsor_id")),
    P("perk.reopened", "Sponsor perk reopened", ("perk_id", "sponsor_id")),
    P("calendar_feed.created", "Personal calendar link created", ("kind",)),
    P("calendar_feed.rotated", "Personal calendar link replaced", ("kind",)),
    P("calendar_feed.revoked", "Personal calendar link revoked", ("kind",)),
)
