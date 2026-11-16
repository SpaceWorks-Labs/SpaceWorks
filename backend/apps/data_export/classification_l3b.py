"""Decision 223 (k), lane L3b: literal export classification for minors, volunteer hours and organization bookings.

* Minors. A profile exports with the space (birth date and guardian contact are scoped PII, decrypted for the
  export like any other registered field); the data subject is the minor's account (`user`), so the profile and
  its consents also travel in that person's subject export. Consent texts and the signed consents are history.
* Volunteer hours and credits are the member's own rows (subject: `member`) and the space's money-adjacent
  history; the `Payment` a credit reduced is exported by the payments ledger.
* The community policy is the Space Manager's own configuration.
* `BookingOrganizationLink` references a deployment-global organization, which never travels with a tenant
  export, so the link is omitted like `EventOrganizer`; the booking and its charge travel without it.
"""
from .types import TenantPredicate as P

POLICY = ("minors_admitted minors_minimum_age adult_age guardian_must_be_present minors_may_borrow "
          "minors_may_use_machines consent_valid_days volunteer_minutes_per_credit volunteer_credit_kind "
          "volunteer_credit_amount volunteer_credit_days join_followup_enabled join_followup_delay_hours")

EXPORTED_FIELDS = {
    "makerspaces.CommunityPolicy": f"id makerspace {POLICY} updated_by updated_at",
    "makerspaces.GuardianConsentTerms": "id makerspace body version is_active created_by created_at superseded_at",
    "makerspaces.MinorProfile": "id makerspace user date_of_birth declared_under_age guardian_user guardian_name "
                                "guardian_email guardian_phone recorded_by cleared_at created_at updated_at",
    "makerspaces.GuardianConsent": "id profile makerspace terms terms_version method signed_name guardian_user "
                                   "recorded_by signed_at valid_until revoked_at revoked_by operation_id",
    "makerspaces.VolunteerHourEntry": "id makerspace member minutes worked_on description source source_ref status "
                                      "submitted_by reviewed_by reviewed_at review_note created_at",
    "makerspaces.VolunteerCredit": "id makerspace member minutes_converted kind amount days currency status "
                                   "applied_payment applied_amount applied_at split_from void_reason created_by "
                                   "created_at",
}
OMITTED_FIELDS = {
    "bookings.BookingOrganizationLink": "id booking makerspace organization organization_name billed_member "
                                        "created_by created_at",
    # B13: the organization hours bank references the same deployment-global organization.
    "bookings.OrganizationHoursAllowance": "id makerspace organization allowance_minutes period updated_by created_at updated_at",
    "bookings.OrganizationHoursLedger": "id makerspace organization booking entry minutes period_key generation reverses reason actor created_at",
}
OMITTED_MODELS = {
    "bookings.BookingOrganizationLink": (
        "It references a deployment-global organization that does not travel with a tenant export; the booking "
        "and its charge travel without the link."
    ),
    "bookings.OrganizationHoursAllowance": (
        "It references a deployment-global organization that does not travel with a tenant export; the "
        "organization hours bank is re-granted by the target's staff."
    ),
    "bookings.OrganizationHoursLedger": (
        "It references a deployment-global organization that does not travel with a tenant export; the "
        "bookings and their charges travel without the organization hours ledger."
    ),
}
DATASET_SPECS = {
    "makerspaces.CommunityPolicy": ("members/community_policy.csv", P(("makerspace",))),
    "makerspaces.GuardianConsentTerms": ("members/guardian_consent_terms.csv", P(("makerspace",))),
    "makerspaces.MinorProfile": ("members/minor_profiles.csv", P(("makerspace",))),
    "makerspaces.GuardianConsent": ("members/guardian_consents.csv", P(("makerspace",))),
    "makerspaces.VolunteerHourEntry": ("members/volunteer_hours.csv", P(("makerspace",))),
    "makerspaces.VolunteerCredit": ("members/volunteer_credits.csv", P(("makerspace",))),
}
SUBJECT_PATHS = {
    "makerspaces.MinorProfile": ("user",),
    "makerspaces.GuardianConsent": ("profile__user",),
    "makerspaces.VolunteerHourEntry": ("member",),
    "makerspaces.VolunteerCredit": ("member",),
}
RELATIONAL_USER_FIELDS = frozenset({
    ("makerspaces.CommunityPolicy", "updated_by"),
    ("makerspaces.GuardianConsentTerms", "created_by"),
    ("makerspaces.MinorProfile", "user"),
    ("makerspaces.MinorProfile", "guardian_user"),
    ("makerspaces.MinorProfile", "recorded_by"),
    ("makerspaces.GuardianConsent", "guardian_user"),
    ("makerspaces.GuardianConsent", "recorded_by"),
    ("makerspaces.GuardianConsent", "revoked_by"),
    ("makerspaces.VolunteerHourEntry", "member"),
    ("makerspaces.VolunteerHourEntry", "submitted_by"),
    ("makerspaces.VolunteerHourEntry", "reviewed_by"),
    ("makerspaces.VolunteerCredit", "member"),
    ("makerspaces.VolunteerCredit", "created_by"),
    ("bookings.BookingOrganizationLink", "billed_member"),
    ("bookings.BookingOrganizationLink", "created_by"),
    ("bookings.OrganizationHoursAllowance", "updated_by"),
    ("bookings.OrganizationHoursLedger", "actor"),
})
