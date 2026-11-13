"""Release 0.12.0 lane L3a (decision 223 (k)): induction events, supervised sessions, incidents.

All three are off by default and leave no surface when off; every row already recorded is
kept. `machines.induction_events` needs the events module (the event is the source of the
grant). `safety.incidents` is a standalone capability served by the maintenance app: it
spans machines, lending, events and rooms, so it has no single parent module.
"""


def definitions(feature):
    return (
        feature(
            "machines.induction_events", "machines", "Induction events",
            "Mark an event as an induction for a machine certification. After it, staff grant that "
            "certification to the attendees who checked in, one audited grant each; guest-pass holders "
            "can be certified too.",
            requires_modules=("events",),
        ),
        feature(
            "machines.supervised_sessions", "machines", "Supervised workshop sessions",
            "A certified instructor opens a supervised session on a machine, adds supervisees, and each "
            "supervisee's use is recorded under the instructor while the session is open.",
        ),
        feature(
            "safety.incidents", None, "Incident register",
            "A space-level register of safety incidents and near misses: members report, staff triage, "
            "area managers see their own area, with follow-up actions and links to loans, bookings, "
            "events and repairs.",
            app_label="maintenance",
        ),
    )
