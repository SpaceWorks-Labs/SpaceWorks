"""Account-merge dispositions for decision 223 (k), lane L3b (minors, volunteer hours and credit, organization bookings)."""

from .merge_registry_types import KEEP_ON_SHELL as K, REPOINT as R, UNIQUE_RESOLVE as U

ROWS = (
    (R, "makerspaces.CommunityPolicy", "updated_by", "Mutable attribution; moves to the survivor."),
    (R, "makerspaces.GuardianConsentTerms", "created_by", "Mutable attribution; moves to the survivor."),
    (U, "makerspaces.MinorProfile", "user",
     "One minor record per person and space; the survivor's wins, the loser's stays on the shell."),
    (R, "makerspaces.MinorProfile", "guardian_user recorded_by", "Mutable attribution; moves to the survivor."),
    (K, "makerspaces.GuardianConsent", "guardian_user recorded_by revoked_by",
     "A signed consent is accountability history; actor_ids_for follows the alias."),
    (R, "makerspaces.VolunteerHourEntry", "member submitted_by reviewed_by",
     "Hours belong to the person who gave them; they move to the survivor."),
    (R, "makerspaces.VolunteerCredit", "member created_by", "Credits follow the person to the survivor."),
    (R, "bookings.BookingOrganizationLink", "billed_member created_by",
     "The contact the debt was recorded against moves to the survivor."),
    (R, "bookings.OrganizationHoursAllowance", "updated_by", "Mutable attribution; moves to the survivor."),
    (K, "bookings.OrganizationHoursLedger", "actor",
     "An append-only hours ledger row is accountability history; actor_ids_for follows the alias."),
)
