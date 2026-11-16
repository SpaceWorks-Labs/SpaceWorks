"""Release-2 lane L2: communications, analytics and programme closures (#71, #73, #95).

Each switch keeps its data when turned off (#95, #128 C-8):

* `events.broadcast_templates` -- the starter-template gallery and the three newer brand
  designs (accent band, photo header, letter). The five-second undo hold, delivery
  tallies and draft autosave are refinements of `events.broadcasts` itself.
* `events.approval_digest` -- one 30-minute digest per organiser while approvals wait.
* `events.anonymous_feedback` -- the per-form anonymous switch. ON by default because
  anonymous feedback forms already existed before the switch did (no behaviour change).
* `events.submission_integrity` -- the informational GitHub first-commit flag job (#8).
* `events.mentor_chat_alerts` -- Mentor Desk help alerts posted to chosen chat rooms.
* `events.organization_sender` -- a co-hosting organisation's sender name and reply-to.
* `notifications.escalation`, `notifications.web_push`, `notifications.inbox_snooze`.
"""


def definitions(feature):
    return (
        feature(
            "events.broadcast_templates", "events", "Broadcast templates and designs",
            "Starter templates and the accent-band, photo-header and letter email designs.",
            requires_features=("events.broadcasts",),
        ),
        feature(
            "events.approval_digest", "events", "Approval digest",
            "Email organisers one summary every 30 minutes while sign-ups wait for approval.",
            requires_modules=("events", "notifications"),
        ),
        feature(
            "events.anonymous_feedback", "events", "Anonymous feedback forms",
            "Let a feedback form collect answers with no link to the person (certificates off only).",
            default_enabled=True,
        ),
        feature(
            "events.submission_integrity", "events", "GitHub first-commit flag",
            "Show judges and organisers when a repository has commits from before kickoff. "
            "Information only: it never disqualifies or hides a project.",
            requires_features=("events.hackathons",),
        ),
        feature(
            "events.mentor_chat_alerts", "events", "Mentor help chat alerts",
            "Post new Mentor Desk help requests to chosen team chat rooms while mentors are on shift.",
            requires_features=("events.mentoring",),
        ),
        feature(
            "events.organization_sender", "events", "Co-host sender name",
            "Event email from a co-hosting organisation shows its sender name and reply-to.",
            requires_modules=("events", "email"),
        ),
        feature(
            "notifications.escalation", "notifications", "Escalation re-ping",
            "Re-ping staff rooms when an urgent staff notice is not seen in time.",
        ),
        feature(
            "notifications.web_push", "notifications", "Browser notifications",
            "People may opt in to browser notifications for their inbox (needs VAPID keys).",
        ),
        feature(
            "notifications.inbox_snooze", "notifications", "Inbox snooze and archive",
            "Snooze an inbox message until later, or archive it out of the list.",
        ),
    )
