"""Decision 314(c): the background-eraser adapter for ID card photos (OFF by default, data kept when off).

* `cards.photo_cutout` -- staff and members can ask a configured eraser service to cut the holder out of their
  card photo; the cut-out is stored next to the original, which is kept. Needs a provider (the platform's or the
  space's own); the holder's photo is sent to it, so members are told and opt in on their own card. The bulk photo
  upload's "Remove backgrounds after upload" option is shown only while this is on and a provider is configured.
"""


def definitions(feature):
    return (
        feature("cards.photo_cutout", "membership", "Card photo background eraser",
                "Cut the holder out of a card photo with your eraser service. The original photo is kept, "
                "and members agree before their photo is sent to the service."),
    )
