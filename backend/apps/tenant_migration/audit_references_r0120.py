"""0.12.0 audit meta ids found by the consolidation drift guard (all rows travel; user ids are snapshots)."""
from .audit_references_targets import AuditReference, AuditReferenceDisposition

R = AuditReferenceDisposition.REMAP
S = AuditReferenceDisposition.SOURCE_LOCAL_SNAPSHOT

EDGES = {
    ("booking.cancelled_event_room_confirmed", "booking_id"): AuditReference(R, "bookings.Booking"),
    ("event.created_with_room", "booking_id"): AuditReference(R, "bookings.Booking"),
    ("card_design.archived", "design_id"): AuditReference(R, "card_designs.CardDesign"),
    ("card_design.unarchived", "design_id"): AuditReference(R, "card_designs.CardDesign"),
    ("id_programme.archived", "programme_id"): AuditReference(R, "id_programmes.IdProgramme"),
    ("id_programme.unarchived", "programme_id"): AuditReference(R, "id_programmes.IdProgramme"),
    ("issue.dispatched", "machine_id"): AuditReference(R, "machines.Machine"),
    ("membership.guest_pass_charge_redirected", "request_id"): AuditReference(R, "hardware_requests.HardwareRequest"),
    ("membership.guest_pass_charge_redirected", "payment_id"): AuditReference(R, "payments.Payment"),
    ("membership.guest_pass_charge_redirected", "guest_id"): AuditReference(S, "accounts.User"),
    ("membership.guest_pass_charge_redirected", "sponsor_id"): AuditReference(S, "accounts.User"),
    ("membership.guest_pass_kept_on_cancel", "registration_id"): AuditReference(R, "events.EventRegistration"),
    ("membership.guest_pass_kept_on_cancel", "event_id"): AuditReference(R, "events.Event"),
    ("event.workshop_machine_unlinked", "link_id"): AuditReference(R, "events.EventMachineBookingLink"),
    ("wallet_pass.guest_issued", "pass_id"): AuditReference(R, "makerspaces.GuestPass"),
    # E-B1: badge designs.
    ("card_design.badge_converted", "design_id"): AuditReference(R, "card_designs.CardDesign"),
    ("card_design.role_variant_created", "design_id"): AuditReference(R, "card_designs.CardDesign"),
    # E-B1/E-B2/E-B3 and the 0.12.0 hosting / notification lanes: ids the drift guard found in audit meta.
    ("card_design.org_default_created", "design_id"): AuditReference(R, "card_designs.CardDesign"),
    ("card_design.org_default_created", "organization_id"): AuditReference(S, "organizations.Organization"),
    ("card_number_scheme.published", "design_id"): AuditReference(R, "card_designs.CardDesign"),
    ("card_number_scheme.published", "scheme_id"): AuditReference(R, "card_designs.CardNumberScheme"),
    ("card_number_scheme.published", "title_id"): AuditReference(R, "makerspaces.MembershipTitle"),
    ("card_number_scheme.updated", "scheme_id"): AuditReference(R, "card_designs.CardNumberScheme"),
    ("card_number_scheme.updated", "title_id"): AuditReference(R, "makerspaces.MembershipTitle"),
    ("card_verification.staff_viewed", "card_id"): AuditReference(R, "makerspaces.MemberCard"),
    ("event.crew.reordered", "event_id"): AuditReference(R, "events.Event"),
    ("event.crew.updated", "crew_id"): AuditReference(R, "events.EventCrewMember"),
    ("event.crew.updated", "event_id"): AuditReference(R, "events.Event"),
    ("event.submission_reinstated", "event_id"): AuditReference(R, "events.Event"),
    ("event.submission_reinstated", "stage_id"): AuditReference(R, "events.SubmissionStage"),
    ("makerspace.created", "hosting_request_id"): AuditReference(S, "hosting_requests.HostingRequest"),
    ("member_card.auto_issue_skipped", "membership_id"): AuditReference(R, "makerspaces.MakerspaceMembership"),
    ("notification_destination.secret_rotated", "destination_id"): AuditReference(R, "integrations.NotificationDestination"),
}
