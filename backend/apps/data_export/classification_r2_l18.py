"""Release-2 lane L18 (donations, pledges, sponsors, personal calendar links): export classification.

Exported with the space: donation settings (page text, the 80G registration), campaigns and
funds, gifts and pledges, sponsors, tiers, perks, sponsorship charges and event links. Donor
and sponsor-contact details are scoped PII (`encryption/registry_r2_l18`); the donor PAN is
ALWAYS encrypted and travels only as its envelope (reports read `Payment` rows, never a PAN).

Omitted, deliberately: a guest's link secret (`access_secret`, `manage_secret`), which is
bearer material (a moved space's guests get fresh links), and `events.PersonalCalendarFeed`,
a source-bound bearer feed the person re-issues on the target.
"""

from .types import TenantPredicate as P

EXPORTED_FIELDS = {
    "payments.DonationSettings": "id makerspace page_intro suggested_amounts minimum_amount "
                                 "tax_exempt_registration_number tax_exempt_valid_from tax_exempt_valid_until "
                                 "tax_exempt_registrant_pan tax_exempt_note updated_by updated_at",
    "payments.DonationCampaign": "id makerspace kind name slug description goal_amount currency starts_at ends_at "
                                 "is_active is_public created_by created_at updated_at",
    "payments.DonationPledge": "id makerspace campaign donor donor_name donor_email amount currency interval starts_on "
                               "next_due_on ends_on status wants_tax_receipt donor_pan donor_address manage_secret "
                               "created_by created_at updated_at cancelled_at last_reminded_on",
    "payments.Donation": "id makerspace campaign pledge period_start donor donor_name donor_email donor_note amount "
                         "currency source status wants_tax_receipt donor_pan donor_address tax_receipt access_secret "
                         "created_by created_at paid_at cancelled_at",
    "payments.SponsorTier": "id makerspace name rank amount currency description created_at",
    "payments.Sponsor": "id makerspace name organization tier logo_key website_url blurb contact_name contact_email "
                        "contact_phone starts_on ends_on show_on_wall created_by created_at updated_at archived_at",
    "payments.SponsorPerk": "id makerspace tier sponsor source_perk description due_on fulfilled_at fulfilled_by note "
                            "reminded_on created_at",
    "payments.SponsorshipCharge": "id makerspace sponsor amount currency description created_by created_at",
    "payments.SponsorEventLink": "id makerspace sponsor event_sponsor created_by created_at",
}
OMITTED_MODELS = {
    "events.PersonalCalendarFeed": "Source-bound personal calendar bearer link; the person issues a new one on the target.",
}
_SECRET = "Random secret bound into a guest's signed link; a moved space's guests get fresh links."
ALWAYS_OMITTED = {
    ("payments.Donation", "access_secret"): _SECRET,
    ("payments.DonationPledge", "manage_secret"): _SECRET,
}
DATASET_SPECS = {
    "payments.DonationSettings": ("finance/donation_settings.csv", P(("makerspace",))),
    "payments.DonationCampaign": ("finance/donation_campaigns.csv", P(("makerspace",))),
    "payments.DonationPledge": ("finance/donation_pledges.csv", P(("makerspace",))),
    "payments.Donation": ("finance/donations.csv", P(("makerspace",))),
    "payments.SponsorTier": ("finance/sponsor_tiers.csv", P(("makerspace",))),
    "payments.Sponsor": ("finance/sponsors.csv", P(("makerspace",))),
    "payments.SponsorPerk": ("finance/sponsor_perks.csv", P(("makerspace",))),
    "payments.SponsorshipCharge": ("finance/sponsorship_charges.csv", P(("makerspace",))),
    "payments.SponsorEventLink": ("finance/sponsor_event_links.csv", P(("makerspace",))),
}
RELATIONAL_USER_FIELDS = frozenset({
    ("payments.DonationSettings", "updated_by"),
    ("payments.DonationCampaign", "created_by"),
    ("payments.DonationPledge", "donor"),
    ("payments.DonationPledge", "created_by"),
    ("payments.Donation", "donor"),
    ("payments.Donation", "created_by"),
    ("payments.Sponsor", "created_by"),
    ("payments.SponsorPerk", "fulfilled_by"),
    ("payments.SponsorshipCharge", "created_by"),
    ("payments.SponsorEventLink", "created_by"),
    ("events.PersonalCalendarFeed", "user"),
})
EXCLUDED_USER_EDGE_REASONS = {
    ("events.PersonalCalendarFeed", "user"): "Source bearer calendar link is omitted; the person re-issues it.",
}
# The frozen 80G receipt (registration, number, amounts, dates) and the suggested amounts: no ids.
JSON_FIELDS = frozenset({("payments.Donation", "tax_receipt"), ("payments.DonationSettings", "suggested_amounts")})


def extend(fields):
    fields.update(EXPORTED_FIELDS)
    return fields
