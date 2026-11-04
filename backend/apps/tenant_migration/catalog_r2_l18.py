"""Release-2 lane L18 (donations, pledges, sponsors, calendar links): tenant-dump catalogue.

Gifts, pledges, campaigns, sponsor rows and the donation settings travel with the space
(data_export `classification_r2_l18`); the frozen 80G receipt travels unchanged. A guest's
link secrets are replaced on the target (`omitted_fields`): guests get fresh links. The
encrypted PAN travels as its scoped-PII envelope. A personal calendar link is a source-bound
bearer credential and is dropped, like the booking and maintenance feeds.
"""

FIELD_NAMES = {
    "payments.DonationSettings": "id makerspace page_intro suggested_amounts minimum_amount "
                                 "tax_exempt_registration_number tax_exempt_valid_from tax_exempt_valid_until "
                                 "tax_exempt_registrant_pan tax_exempt_note updated_by updated_at",
    "payments.DonationCampaign": "id makerspace kind name slug description goal_amount currency starts_at ends_at "
                                 "is_active is_public created_by created_at updated_at",
    "payments.DonationPledge": "id makerspace campaign donor donor_name donor_email amount currency interval starts_on "
                               "next_due_on ends_on status wants_tax_receipt tax_detail manage_secret "
                               "created_by created_at updated_at cancelled_at last_reminded_on",
    "payments.Donation": "id makerspace campaign pledge period_start donor donor_name donor_email donor_note amount "
                         "currency source status wants_tax_receipt tax_detail tax_receipt access_secret "
                         "created_by created_at paid_at cancelled_at",
    "payments.DonorTaxDetail": "id makerspace pan address created_at",
    "payments.SponsorTier": "id makerspace name rank amount currency description created_at",
    "payments.Sponsor": "id makerspace name organization tier logo_key website_url blurb contact_name contact_email "
                        "contact_phone starts_on ends_on show_on_wall created_by created_at updated_at archived_at",
    "payments.SponsorPerk": "id makerspace tier sponsor source_perk description due_on fulfilled_at fulfilled_by note "
                            "reminded_on created_at",
    "payments.SponsorshipCharge": "id makerspace sponsor amount currency description created_by created_at",
    "payments.SponsorEventLink": "id makerspace sponsor event_sponsor created_by created_at",
    "events.PersonalCalendarFeed": "id makerspace user kind token_digest token_hint created_at rotated_at revoked_at",
}
FIELD_NAMES = {label: frozenset(names.split()) for label, names in FIELD_NAMES.items()}
EXTRA_FIELDS = {}
PROJECTED_LABELS = frozenset(label for label in FIELD_NAMES if label != "events.PersonalCalendarFeed")


def authority_entries(authority, disposition):
    def same(label, names, chosen, reason):
        return tuple(((label, name), authority(chosen, reason)) for name in names.split())

    keep = disposition.PRESERVE
    return (
        *same("payments.Donation", "amount currency source status wants_tax_receipt tax_receipt created_at paid_at "
              "cancelled_at", keep, "A gift and its frozen 80G receipt are the space's money history; never recomputed."),
        *same("payments.DonationPledge", "amount currency interval starts_on next_due_on ends_on status "
              "wants_tax_receipt cancelled_at last_reminded_on", keep,
              "A pledge's promise and schedule; the target raises the next period on its own clock."),
        *same("payments.SponsorshipCharge", "amount currency created_at", keep,
              "What a sponsor agreed to pay; its charge is the ledger row."),
        *same("payments.SponsorPerk", "fulfilled_at reminded_on", keep, "Who-did-what on a sponsor's perk checklist."),
        *same("events.PersonalCalendarFeed", "user token_digest token_hint revoked_at", disposition.DROP,
              "Source calendar tokens never become target disclosure authority; the person re-issues a link."),
    )
