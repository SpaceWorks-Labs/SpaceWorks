"""Analytics views (catalogue version 3): guest passes, inductions and the incident register.

Release 0.12 (decisions 219, 223). People appear as member ids only. Free text is left out on
purpose: no revocation reason, grant notes, incident title, description, location, involved
note or resolution note, no waiver version string and no operation id.
"""

from .types import Col, View

VIEWS = (
    View("day_pass_products", "membership", "Day passes a space sells.",
         "FROM {makerspaces.DayPassProduct} p", "p.makerspace_id", (
             Col("day_pass_product_id", "p.id", "Product id."),
             Col("name", "p.name", "Product name."),
             Col("amount", "p.amount", "Price."),
             Col("currency", "p.currency", "Currency of the price."),
             Col("daily_cap", "p.daily_cap", "Passes sold per day, if capped."),
             Col("is_public", "p.is_public", "Offered on the public page."),
             Col("is_active", "p.is_active", "On sale."),
             Col("archived_at", "p.archived_at", "Archived."),
             Col("created_at", "p.created_at", "Added."),
         ), since=3, requires=("membership.day_passes",)),
    View("guest_passes", "membership",
         "Dated guest permits (event, sponsored, day). Not memberships; never counted as members.",
         "FROM {makerspaces.GuestPass} g", "g.makerspace_id", (
             Col("pass_id", "g.id", "Pass id."),
             Col("member_id", "g.holder_id", "Holder (a person id; not a roster member)."),
             Col("sponsor_member_id", "g.sponsor_id", "Sponsoring member (members)."),
             Col("kind", "g.kind", "Event guest, sponsored guest or day pass."),
             Col("status", "g.status", "Pass state."),
             Col("valid_from", "g.valid_from", "Valid from."),
             Col("valid_until", "g.valid_until", "Valid until."),
             Col("pass_date", "g.pass_date", "Local calendar day of the pass."),
             Col("day_pass_product_id", "g.product_id", "Day pass product (day_pass_products)."),
             Col("borrow_mode", "g.entitlements ->> 'borrow'", "Borrowing the pass allows."),
             Col("machine_mode", "g.entitlements ->> 'machines'", "Machine use the pass allows."),
             Col("waiver_accepted", "(g.accepted_waiver_id IS NOT NULL)", "A waiver was accepted."),
             Col("waiver_accepted_at", "g.waiver_accepted_at", "Waiver accepted."),
             Col("revoked_at", "g.revoked_at", "Revoked."),
             Col("converted", "(g.converted_membership_id IS NOT NULL)", "Converted to a membership."),
             Col("created_at", "g.created_at", "Issued."),
         ), since=3, requires=("membership.guest_passes",)),
    View("guest_certification_grants", "machines",
         "Certifications granted to guests, for example through an induction event.",
         "FROM {machines.GuestCertificationGrant} g", "g.makerspace_id", (
             Col("grant_id", "g.id", "Grant id."),
             Col("certification_type_id", "g.certification_type_id", "Certification type."),
             Col("member_id", "g.user_id", "Guest (a person id; not a roster member)."),
             Col("source_event_id", "g.source_event_id", "Induction event (events)."),
             Col("granted_at", "g.granted_at", "Granted."),
             Col("expires_at", "g.expires_at", "Expires."),
             Col("revoked_at", "g.revoked_at", "Revoked."),
         ), since=3, requires=("machines.induction_events",)),
    View("incidents", "machines",
         "Safety incident and near-miss register: kind, severity, state and links, never the text.",
         "FROM {maintenance.Incident} i", "i.makerspace_id", (
             Col("incident_id", "i.id", "Incident id."),
             Col("kind", "i.kind", "Incident or near miss."),
             Col("severity", "i.severity", "Severity."),
             Col("status", "i.status", "State."),
             Col("area", "i.area", "Area of the space it concerns."),
             Col("occurred_at", "i.occurred_at", "Happened."),
             Col("reporter_member_id", "i.reporter_id", "Reporter (members)."),
             Col("involved_member_id", "i.involved_user_id", "Person involved (members)."),
             Col("machine_id", "i.machine_id", "Machine (machines)."),
             Col("bookable_space_id", "i.room_id", "Room (bookable_spaces)."),
             Col("event_id", "i.event_id", "Event (events)."),
             Col("request_id", "i.loan_id", "Loan request (loan_requests)."),
             Col("booking_id", "i.booking_id", "Booking (bookings)."),
             Col("pass_id", "i.guest_pass_id", "Guest pass (guest_passes.pass_id)."),
             Col("closed_at", "i.closed_at", "Closed."),
             Col("created_at", "i.created_at", "Recorded."),
         ), since=3, requires=("safety.incidents",)),
    View("incident_actions", "machines", "Follow-up actions on incidents; counts and timing, not text.",
         "FROM {maintenance.IncidentAction} a JOIN {maintenance.Incident} i ON i.id = a.incident_id",
         "i.makerspace_id", (
             Col("action_id", "a.id", "Action id."),
             Col("incident_id", "a.incident_id", "Incident (incidents)."),
             Col("assignee_member_id", "a.assignee_id", "Assignee (members)."),
             Col("due_date", "a.due_date", "Due."),
             Col("done_at", "a.done_at", "Done."),
             Col("created_at", "a.created_at", "Created."),
         ), since=3, requires=("safety.incidents",)),
)
