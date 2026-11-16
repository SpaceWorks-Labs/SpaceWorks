"""Release-2 lane r2-peoples-choice: an optional People's choice award for hackathons (#181 S3).

`events.peoples_choice` lets signed-in members vote once per event on public gallery projects; staff
publish the result once, as an extra award beside judging (which it never changes). Off by default;
each event also keeps its own switch, off until an organizer turns it on.
"""


def definitions(feature):
    return (
        feature("events.peoples_choice", "events", "People's choice award",
                "Signed-in members vote for their favourite public gallery project, one vote per person per "
                "event, inside a voting window. Results stay hidden until staff publish them as an extra award; "
                "judging is never changed.", requires_features=("events.project_gallery",)),
    )
