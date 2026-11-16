"""DISPLAY-2 (decision 325): the space's Anthias players, kept in step with its display screens.

* `display.anthias_push` -- register Anthias players and let SpaceWorks create, update and delete the
  matching web assets through the player's REST API. Off = the players section and the sync answer 404;
  the saved players, links and asset ids are kept. Display screens and their links keep working.
"""


def definitions(feature):
    return (
        feature("display.anthias_push", "presence", "Send display screens to Anthias",
                "Register Anthias players and keep each display screen's web asset in step on them.",
                default_enabled=False),
    )
