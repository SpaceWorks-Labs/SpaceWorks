"""Scoped-PII fields added by release-2 lane L3 (ID cards)."""


def id_card_pii_fields(field):
    return (
        field("makerspaces.MemberCard", "revoked_note", "makerspace_id", 500, "source", "none"),
        field("card_designs.CardHolderExtras", "blood_group", "makerspace_id", 3, "source", "none"),
        field("card_designs.CardHolderExtras", "emergency_contact_name", "makerspace_id", 80, "source", "none"),
        field("card_designs.CardHolderExtras", "emergency_contact_phone", "makerspace_id", 32, "source", "none"),
        field("id_programmes.IdProgrammeCard", "name", "makerspace_id", 120, "source", "none"),
        field("id_programmes.IdProgrammeCard", "email", "makerspace_id", 254, "source", "none"),
        field("id_programmes.IdProgrammeCard", "answers", "makerspace_id", None, "source", "none"),
        field("id_programmes.IdProgrammeCard", "status_reason", "makerspace_id", 300, "source", "none"),
        field("events.EventIdCard", "printed_name", "makerspace_id", 200, "source", "none"),
        field("events.EventIdCard", "revoked_reason", "makerspace_id", 300, "source", "none"),
    )
