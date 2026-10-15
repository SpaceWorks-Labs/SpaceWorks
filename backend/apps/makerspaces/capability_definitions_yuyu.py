"""Approved parity capabilities, picked up by the installer through their parents."""


def definitions(FeatureDefinition):
    return (FeatureDefinition(
        "events.organization_audience", "events", "Participating organizations audience",
        "Admit active accounts belonging to live event organizers or the venue owner, "
        "directly or through their owned makerspaces. Imported audiences need local review.",
        requires_modules=("events",),
    ),)
