"""Scoped-PII fields added by release-2 lane L18 (donations, pledges and sponsors).

The 80G PAN is `encryption_required`: it is enciphered on every deployment, with or without
`PII_ENCRYPTION_ENABLED`, exactly like event payee bank details (#128 C-14d).
"""


def donation_pii_fields(field):
    return (
        field("payments.Donation", "donor_name", "makerspace_id", 200, "source", "none"),
        field("payments.Donation", "donor_email", "makerspace_id", 254, "source", "none"),
        field("payments.Donation", "donor_note", "makerspace_id", 500, "source", "none"),
        field("payments.DonorTaxDetail", "pan", "makerspace_id", 10, "source", "none", True),
        field("payments.DonorTaxDetail", "address", "makerspace_id", 500, "source", "none"),
        field("payments.DonationPledge", "donor_name", "makerspace_id", 200, "source", "none"),
        field("payments.DonationPledge", "donor_email", "makerspace_id", 254, "source", "none"),
        field("payments.Sponsor", "contact_name", "makerspace_id", 200, "source", "none"),
        field("payments.Sponsor", "contact_email", "makerspace_id", 254, "source", "none"),
        field("payments.Sponsor", "contact_phone", "makerspace_id", 32, "source", "none"),
    )
