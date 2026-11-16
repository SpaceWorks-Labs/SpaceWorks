"""Off-by-default programme capabilities, all children of the existing Events module."""


def programme_features(feature):
    return (
        feature("events.hackathons", "events", "Hackathon programmes"),
        # Mentor Desk works on any event (#128 C-36, E2-f): a hackathon's teams ask as teams,
        # anyone else drops in on their own. Check-in rounds visit teams, so they stay hackathon-only.
        feature("events.mentoring", "events", "Mentor desk"),
        feature("events.mentor_rounds", "events", "Mentor check-in rounds",
                requires_features=("events.mentoring", "events.hackathons")),
        feature("events.volunteering", "events", "Volunteer contributions"),
        feature("events.project_gallery", "events", "Project gallery", requires_features=("events.hackathons",)),
        feature("events.pairwise_judging", "events", "Pairwise judging", requires_features=("events.hackathons",)),
    )
