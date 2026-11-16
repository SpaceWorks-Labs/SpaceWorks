"""Scoped-PII fields added by release-2 lane L4 (membership lifecycle)."""


def membership_lifecycle_pii_fields(field):
    return (
        field("makerspaces.MembershipRecord", "gstin", "makerspace_id", 15, "source", "none"),
        field("makerspaces.MembershipRecord", "staff_notes", "makerspace_id", 4000, "source", "none"),
        field("makerspaces.MembershipErasureRequest", "member_note", "makerspace_id", 1000, "source", "none"),
        field("makerspaces.ImportedMember", "name", "makerspace_id", 200, "source", "none"),
        field("makerspaces.ImportedMember", "email", "makerspace_id", 254, "source", "none"),
        field("makerspaces.ImportedMember", "phone", "makerspace_id", 32, "source", "none"),
        field("makerspaces.ImportedMember", "gstin", "makerspace_id", 15, "source", "none"),
        field("makerspaces.ImportedMember", "staff_notes", "makerspace_id", 4000, "source", "none"),
    )
