"""Parity E-B4: the judging scores CSV (OFF by default).

* `events.scores_export` -- export every judging round's scores as CSV: rank, reviews, raw and adjusted
  score, one average per criterion and the names of the judges who scored. Never carries comments,
  private notes or email addresses. Requires `events.hackathons`. Off = the route answers 404.

Reinstating a disqualified project, unpublishing results and the assignment preview are fixes to existing
hackathon workflows, so they have no switch of their own.
"""


def definitions(feature):
    return (
        feature("events.scores_export", "events", "Judging scores export",
                "Download the judging scores of an event as CSV: raw and adjusted score, per-criterion "
                "averages and judge names, without comments or email addresses.",
                requires_features=("events.hackathons",)),
    )
