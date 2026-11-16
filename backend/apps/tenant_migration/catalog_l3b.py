"""Decision 223 (k), lane L3b: tenant-dump field snapshot, authority, uniqueness and audit meta edges.

Minors, guardian consents and texts, volunteer hours and credits, and the community policy travel with the
space (data_export `classification_l3b`); foreign keys remap like any other. The consent texts and signatures
are the space's own accountability history and are preserved as written; the target's own switches decide
whether any of it is enforced. `BookingOrganizationLink` is listed for the field snapshot only: it references a
deployment-global organization that does not travel, so it is omitted (data_export OMITTED_MODELS).
"""
# Kept literal (not imported from data_export): the dump snapshot is a pinned, independent record.
_POLICY = ("minors_admitted minors_minimum_age adult_age guardian_must_be_present minors_may_borrow "
           "minors_may_use_machines consent_valid_days volunteer_minutes_per_credit volunteer_credit_kind "
           "volunteer_credit_amount volunteer_credit_days join_followup_enabled join_followup_delay_hours")
_FIELDS = {
    "makerspaces.CommunityPolicy": f"id makerspace {_POLICY} updated_by updated_at",
    "makerspaces.GuardianConsentTerms": "id makerspace body version is_active created_by created_at superseded_at",
    "makerspaces.MinorProfile": ("id makerspace user date_of_birth declared_under_age guardian_user guardian_name "
                                 "guardian_email guardian_phone recorded_by cleared_at created_at updated_at"),
    "makerspaces.GuardianConsent": ("id profile makerspace terms terms_version method signed_name guardian_user "
                                    "recorded_by signed_at valid_until revoked_at revoked_by operation_id"),
    "makerspaces.VolunteerHourEntry": ("id makerspace member minutes worked_on description source source_ref status "
                                       "submitted_by reviewed_by reviewed_at review_note created_at"),
    "makerspaces.VolunteerCredit": ("id makerspace member minutes_converted kind amount days currency status "
                                    "applied_payment applied_amount applied_at split_from void_reason created_by "
                                    "created_at"),
}
PROJECTED_LABELS = frozenset(_FIELDS)
FIELD_NAMES = {label: frozenset(names.split()) for label, names in _FIELDS.items()}
FIELD_NAMES["bookings.BookingOrganizationLink"] = frozenset(
    "id booking makerspace organization organization_name billed_member created_by created_at".split())
# B13: the organization hours bank, listed for the field snapshot only (omitted from the dump like the link).
FIELD_NAMES["bookings.OrganizationHoursAllowance"] = frozenset("id makerspace organization allowance_minutes period updated_by created_at updated_at".split())
FIELD_NAMES["bookings.OrganizationHoursLedger"] = frozenset("id makerspace organization booking entry minutes period_key generation reverses reason actor created_at".split())

_PRESERVED = {
    "makerspaces.CommunityPolicy": f"{_POLICY} updated_at",
    "makerspaces.GuardianConsentTerms": "body version is_active created_at superseded_at",
    "makerspaces.MinorProfile": ("date_of_birth declared_under_age guardian_name guardian_email guardian_phone "
                                 "cleared_at created_at updated_at"),
    "makerspaces.GuardianConsent": ("terms_version method signed_name signed_at valid_until revoked_at "
                                    "operation_id"),
    "makerspaces.VolunteerHourEntry": ("minutes worked_on description source source_ref status reviewed_at "
                                       "review_note created_at"),
    "makerspaces.VolunteerCredit": ("minutes_converted kind amount days currency status applied_amount applied_at "
                                    "void_reason created_at"),
}


def authority_entries(authority, disposition):
    keep = disposition.PRESERVE
    return tuple(
        ((label, name), authority(keep, "The space's own minors, consent, volunteer or policy record; the target's "
                                        "switches decide whether it is enforced."))
        for label, names in _PRESERVED.items() for name in names.split())


def unique_rules(remap, policy):
    """None: minors, consent and volunteer uniqueness is scoped by the space, so it is tenant-owned, not global."""
    return {}
