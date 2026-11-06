"""Audit presentation for lane L18: donations, pledges, sponsors and personal calendar links.

Metadata is ids, amounts, statuses and switches only. A donor's or sponsor contact's name,
email, address, note and PAN are never in an audit row; neither is a feed token.
"""

from django.utils.translation import gettext_lazy
from .presentation_catalog_types import P

_GIFT = ("donation_id", "payment_id", "amount", "currency", "source", "campaign_id", "pledge_id", "guest",
         "tax_receipt_requested")
_PLEDGE = ("pledge_id", "status")

ENTRIES = (
    P("donation.created", gettext_lazy("Donation recorded"), _GIFT),
    P("donation.paid", gettext_lazy("Donation received"), ("donation_id", "status", "tax_receipt")),
    P("donation.cancelled", gettext_lazy("Donation cancelled"), ("donation_id", "status", "reason_given")),
    P("donation.return_case_opened", gettext_lazy("Refund case opened to return a gift"), ("case_id", "payment_id", "subject_type")),
    P("donation.campaign_created", gettext_lazy("Donation campaign created"), ("campaign_id", "kind")),
    P("donation.campaign_updated", gettext_lazy("Donation campaign changed"), ("campaign_id", "fields")),
    P("pledge.created", gettext_lazy("Donation pledge made"), ("pledge_id", "amount", "currency", "interval", "guest", "campaign_id")),
    P("pledge.paused", gettext_lazy("Donation pledge paused"), _PLEDGE),
    P("pledge.resumed", gettext_lazy("Donation pledge resumed"), _PLEDGE),
    P("pledge.updated", gettext_lazy("Donation pledge changed"), _PLEDGE),
    P("pledge.cancelled", gettext_lazy("Donation pledge cancelled"), _PLEDGE),
    P("pledge.period_raised", gettext_lazy("Pledge period charge raised"), ("pledge_id", "donation_id", "period_start")),
    P("sponsor.created", gettext_lazy("Sponsor added"), ("sponsor_id", "fields")),
    P("sponsor.updated", gettext_lazy("Sponsor changed"), ("sponsor_id", "fields")),
    P("sponsor.archived", gettext_lazy("Sponsor archived"), ("sponsor_id",)),
    P("sponsor.restored", gettext_lazy("Sponsor restored"), ("sponsor_id",)),
    P("sponsor.tier_created", gettext_lazy("Sponsor tier created"), ("tier_id",)),
    P("sponsor.tier_updated", gettext_lazy("Sponsor tier changed"), ("tier_id", "fields")),
    P("sponsor.charge_raised", gettext_lazy("Sponsorship payment recorded as owed"), ("sponsor_id", "charge_id", "payment_id",
                                                                        "amount")),
    P("sponsor.charge_paid", gettext_lazy("Sponsorship payment received"), ("sponsor_id", "charge_id", "payment_id", "status")),
    P("sponsor.event_linked", gettext_lazy("Sponsor linked to an event"), ("sponsor_id", "event_sponsor_id", "event_id")),
    P("sponsor.event_unlinked", gettext_lazy("Sponsor unlinked from an event"), ("sponsor_id", "event_sponsor_id")),
    P("sponsor.logo_updated", gettext_lazy("Sponsor logo changed"), ("sponsor_id",)),
    P("sponsor.logo_removed", gettext_lazy("Sponsor logo removed"), ("sponsor_id",)),
    P("perk.copied", gettext_lazy("Tier perks copied to a sponsor"), ("sponsor_id", "tier_id", "count")),
    P("perk.created", gettext_lazy("Sponsor perk added"), ("perk_id", "sponsor_id", "tier_id")),
    P("perk.updated", gettext_lazy("Sponsor perk changed"), ("perk_id", "sponsor_id", "tier_id")),
    P("perk.fulfilled", gettext_lazy("Sponsor perk fulfilled"), ("perk_id", "sponsor_id")),
    P("perk.reopened", gettext_lazy("Sponsor perk reopened"), ("perk_id", "sponsor_id")),
    P("calendar_feed.created", gettext_lazy("Personal calendar link created"), ("kind",)),
    P("calendar_feed.rotated", gettext_lazy("Personal calendar link replaced"), ("kind",)),
    P("calendar_feed.revoked", gettext_lazy("Personal calendar link revoked"), ("kind",)),
)
