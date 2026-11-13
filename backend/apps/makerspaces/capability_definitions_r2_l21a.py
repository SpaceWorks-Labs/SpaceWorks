"""Release-2 lane L21a: applications for any event, review stages, attendance, crew, check-in lists.

Every key is a capability under `events`, off by default, and keeps its data when turned
off (#95, #128 C-8). Hackathons keep the same admission engine: `events.hackathons` still
opens the application programme on its own, and `events.applications` opens it for any
one-off event (#128 C-32).

* `events.applications` -- an application form, review and offers on any one-off event.
* `events.application_stages` -- multi-stage review: per-stage panels, criteria, blind
  review and a stored-seed reviewer assignment (#128 C-33: 1-20 reviews per application).
* `events.attendance_confirmation` -- "Are you still coming?", sent by staff only (X43).
* `events.crew` -- the event's organising crew: free places outside capacity (#128 C-36).
* `events.crew_claims` -- crew expense claims through event reimbursements.
* `events.checkin_lists` -- extra check-in lists (swag, lunch, workshop), online only (X45).
"""


def definitions(feature):
    return (
        feature("events.applications", "events", "Applications for any event",
                "People apply through a form; staff review, then offer, waitlist or decline places. "
                "Paid places are charged after the place is confirmed."),
        feature("events.application_stages", "events", "Application review stages",
                "Review applications in several stages, each with its own reviewer panel, criteria and "
                "number of reviews per application.", requires_features=("events.applications",)),
        feature("events.attendance_confirmation", "events", "Attendance confirmation",
                "Staff ask registered people whether they are still coming; replies show in the guest list "
                "and at the desk."),
        feature("events.crew", "events", "Event crew",
                "The organising crew: free crew places that never count against capacity, a crew sign-up "
                "link with review, a catering summary and an optional public crew section."),
        feature("events.crew_claims", "events", "Crew expense claims",
                "Crew members claim their expenses through event reimbursements.",
                requires_modules=("event_reimbursements",), requires_features=("events.crew",)),
        feature("events.checkin_lists", "events", "Custom check-in lists",
                "Extra lists for swag, lunch or a workshop, optionally only after entry or only for buyers "
                "of an add-on. They never change entry check-in."),
    )
