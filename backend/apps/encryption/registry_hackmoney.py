"""Scoped-PII fields added by the hack-money lane (#180 G4, #181 G7): a prize winner's claim.

The payee routing details and the PAN are `encryption_required`: enciphered on every deployment,
with or without `PII_ENCRYPTION_ENABLED`, exactly like event payee details and L18's 80G PAN.
"""


def prize_claim_pii_fields(field):
    return (
        field("events.HackathonPrizeClaim", "details", "makerspace_id", None, "source", "none", True),
        field("events.HackathonPrizeClaim", "pan", "makerspace_id", 10, "source", "none", True),
    )
