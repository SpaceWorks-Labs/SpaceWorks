"""Off-by-default programme capabilities, all children of the existing Events module."""


def programme_features(feature):
    return (
        feature("events.hackathons", "events", "Hackathon programmes"),
        feature("events.mentoring", "events", "Mentor desk", requires_features=("events.hackathons",)),
        feature("events.mentor_rounds", "events", "Mentor check-in rounds", requires_features=("events.mentoring",)),
        feature("events.volunteering", "events", "Volunteer contributions"),
        feature("events.project_gallery", "events", "Project gallery", requires_features=("events.hackathons",)),
    )
