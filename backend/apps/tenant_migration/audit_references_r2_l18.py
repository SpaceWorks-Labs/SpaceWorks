"""Audit metadata IDs written by release-2 lane L18 (donations, pledges and sponsors)."""

from .audit_references_targets import AuditReference, AuditReferenceDisposition

R = AuditReferenceDisposition.REMAP


def _remap(model, *edges):
    return {edge: AuditReference(R, model) for edge in edges}


EDGES = {
    **_remap("payments.Donation", ("donation.created", "donation_id"), ("donation.paid", "donation_id"),
             ("donation.cancelled", "donation_id"), ("pledge.period_raised", "donation_id")),
    **_remap("payments.Payment", ("donation.created", "payment_id"), ("donation.return_case_opened", "payment_id"),
             ("sponsor.charge_raised", "payment_id"), ("sponsor.charge_paid", "payment_id")),
    **_remap("payments.RefundCase", ("donation.return_case_opened", "case_id")),
    **_remap("payments.DonationCampaign", ("donation.created", "campaign_id"), ("pledge.created", "campaign_id"),
             ("donation.campaign_created", "campaign_id"), ("donation.campaign_updated", "campaign_id")),
    **_remap("payments.DonationPledge", ("donation.created", "pledge_id"), *((f"pledge.{action}", "pledge_id") for
                                                                             action in ("created", "paused", "resumed",
                                                                                        "updated", "cancelled",
                                                                                        "period_raised"))),
    **_remap("payments.Sponsor", *((f"sponsor.{action}", "sponsor_id") for action in (
        "created", "updated", "archived", "restored", "charge_raised", "charge_paid", "event_linked", "event_unlinked",
        "logo_updated", "logo_removed")), *((f"perk.{action}", "sponsor_id") for action in (
            "copied", "created", "updated", "fulfilled", "reopened"))),
    **_remap("payments.SponsorshipCharge", ("sponsor.charge_raised", "charge_id"), ("sponsor.charge_paid", "charge_id")),
    **_remap("payments.SponsorTier", ("sponsor.tier_created", "tier_id"), ("sponsor.tier_updated", "tier_id"),
             ("perk.copied", "tier_id"), ("perk.created", "tier_id"), ("perk.updated", "tier_id")),
    **_remap("payments.SponsorPerk", *((f"perk.{action}", "perk_id") for action in (
        "created", "updated", "fulfilled", "reopened"))),
    **_remap("events.EventSponsor", ("sponsor.event_linked", "event_sponsor_id"),
             ("sponsor.event_unlinked", "event_sponsor_id")),
    **_remap("events.Event", ("sponsor.event_linked", "event_id")),
}
