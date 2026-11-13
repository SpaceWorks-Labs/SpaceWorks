"""Scoped-PII fields added by lane L3b (decision 223 (k): minors and guardian consent).

A minor's date of birth, the guardian's name, e-mail and phone, and the guardian's typed signature are source
PII, encrypted per makerspace when encryption is enabled. They are never blind-indexed (no search over them).
"""


def minors_pii_fields(field):
    return (
        field("makerspaces.MinorProfile", "date_of_birth", "makerspace_id", 10, "source", "none"),
        field("makerspaces.MinorProfile", "guardian_name", "makerspace_id", 200, "source", "none"),
        field("makerspaces.MinorProfile", "guardian_email", "makerspace_id", 254, "source", "none"),
        field("makerspaces.MinorProfile", "guardian_phone", "makerspace_id", 32, "source", "none"),
        field("makerspaces.GuardianConsent", "signed_name", "makerspace_id", 200, "source", "none"),
    )
