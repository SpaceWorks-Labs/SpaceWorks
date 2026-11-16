"""Audit presentation for lane L18: donations, pledges, sponsors and personal calendar links.

Metadata is ids, amounts, statuses and switches only. A donor's or sponsor contact's name,
email, address, note and PAN are never in an audit row; neither is a feed token.
"""

from django.utils.translation import gettext_noop
from .presentation_catalog_types import P

_GIFT = ("donation_id", "payment_id", "amount", "currency", "source", "campaign_id", "pledge_id", "guest",
         "tax_receipt_requested")
_PLEDGE = ("pledge_id", "status")

ENTRIES = (
    P("donation.created", gettext_noop("Donation recorded"), _GIFT),
    P("donation.paid", gettext_noop("Donation received"), ("donation_id", "status", "tax_receipt")),
    P("donation.cancelled", gettext_noop("Donation cancelled"), ("donation_id", "status", "reason_given")),
    P("donation.return_case_opened", gettext_noop("Refund case opened to return a gift"), ("case_id", "payment_id", "subject_type")),
    P("donation.campaign_created", gettext_noop("Donation campaign created"), ("campaign_id", "kind")),
    P("donation.campaign_updated", gettext_noop("Donation campaign changed"), ("campaign_id", "fields")),
    # Decision 242(m): a gift's receipt sent again (its tax receipt issued if owed), and the gift export.
    P("donation.receipt_reissued", gettext_noop("Donation receipt sent again"), ("donation_id", "tax_receipt")),
    P("donation.exported", gettext_noop("Donations exported"), ("rows", "status", "campaign_id")),
    P("pledge.created", gettext_noop("Donation pledge made"), ("pledge_id", "amount", "currency", "interval", "guest", "campaign_id")),
    P("pledge.paused", gettext_noop("Donation pledge paused"), _PLEDGE),
    P("pledge.resumed", gettext_noop("Donation pledge resumed"), _PLEDGE),
    P("pledge.updated", gettext_noop("Donation pledge changed"), _PLEDGE),
    P("pledge.cancelled", gettext_noop("Donation pledge cancelled"), _PLEDGE),
    P("pledge.period_raised", gettext_noop("Pledge period charge raised"), ("pledge_id", "donation_id", "period_start")),
    P("sponsor.created", gettext_noop("Sponsor added"), ("sponsor_id", "fields")),
    P("sponsor.updated", gettext_noop("Sponsor changed"), ("sponsor_id", "fields")),
    P("sponsor.archived", gettext_noop("Sponsor archived"), ("sponsor_id",)),
    P("sponsor.restored", gettext_noop("Sponsor restored"), ("sponsor_id",)),
    P("sponsor.tier_created", gettext_noop("Sponsor tier created"), ("tier_id",)),
    P("sponsor.tier_updated", gettext_noop("Sponsor tier changed"), ("tier_id", "fields")),
    P("sponsor.charge_raised", gettext_noop("Sponsorship payment recorded as owed"), ("sponsor_id", "charge_id", "payment_id",
                                                                        "amount")),
    P("sponsor.charge_paid", gettext_noop("Sponsorship payment received"), ("sponsor_id", "charge_id", "payment_id", "status")),
    P("sponsor.event_linked", gettext_noop("Sponsor linked to an event"), ("sponsor_id", "event_sponsor_id", "event_id")),
    P("sponsor.event_unlinked", gettext_noop("Sponsor unlinked from an event"), ("sponsor_id", "event_sponsor_id")),
    P("sponsor.logo_updated", gettext_noop("Sponsor logo changed"), ("sponsor_id",)),
    P("sponsor.logo_removed", gettext_noop("Sponsor logo removed"), ("sponsor_id",)),
    P("perk.copied", gettext_noop("Tier perks copied to a sponsor"), ("sponsor_id", "tier_id", "count")),
    P("perk.created", gettext_noop("Sponsor perk added"), ("perk_id", "sponsor_id", "tier_id")),
    P("perk.updated", gettext_noop("Sponsor perk changed"), ("perk_id", "sponsor_id", "tier_id")),
    P("perk.fulfilled", gettext_noop("Sponsor perk fulfilled"), ("perk_id", "sponsor_id")),
    P("perk.reopened", gettext_noop("Sponsor perk reopened"), ("perk_id", "sponsor_id")),
    P("calendar_feed.created", gettext_noop("Personal calendar link created"), ("kind",)),
    P("calendar_feed.rotated", gettext_noop("Personal calendar link replaced"), ("kind",)),
    P("calendar_feed.revoked", gettext_noop("Personal calendar link revoked"), ("kind",)),
)
