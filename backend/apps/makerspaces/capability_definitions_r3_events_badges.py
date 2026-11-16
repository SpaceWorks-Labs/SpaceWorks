"""Parity E-B1/E-B2: the Events badge designer, desk printing and role badges (all ON once Events and event ID
cards are on: the owner asked for these features, and they only appear to staff who run an event).

* `events.badge_designer` -- the structured badge designer (`badge_v1`): templates, stock presets, answers on
  the badge, the Events design-file import. Off = its routes answer 404; designs and data are kept.
* `events.badge_desk_print` -- instant print at the check-in desk and station, and the offline roster's badge data.
* `events.role_badges` -- a badge design per role (crew, volunteer, speaker, mentor, judge, organiser) and role
  detection when cards are issued.

All three require `events.id_cards`.
"""


def definitions(feature):
    parent = ("events.id_cards",)
    return (
        feature("events.badge_designer", "events", "Badge designer",
                "Design event badges with the structured badge designer: Classic, Bold or Minimal, badge stock "
                "presets, registration answers, sponsor logos and the check-in QR.",
                default_enabled=True, requires_features=parent),
        feature("events.badge_desk_print", "events", "Desk badge printing",
                "Print each attendee's badge the moment they check in, at the desk or the check-in station, "
                "including while the network is down.",
                default_enabled=True, requires_features=parent),
        feature("events.role_badges", "events", "Role badges",
                "A badge design for crew, volunteers, speakers, mentors, judges and organisers, picked "
                "automatically from each person's role.",
                default_enabled=True, requires_features=parent),
    )
