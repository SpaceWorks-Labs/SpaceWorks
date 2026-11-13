"""Release-2 lane L20: the in-app help centre (#69, #128 C-31).

`platform.help_centre` -- ON by default, standalone (no parent module). While on, the staff
console shows a "Help" link beside each screen and the space's public help routes
(`/help` on a single-space origin, `/m/<slug>/help` on the central one) open the guide.
Off: the links disappear and the space's help routes answer "page not found". The guide
itself is static content bundled with the frontend; it stores nothing, so switching it off
or on loses nothing. The platform-wide `/help` on the central origin belongs to no space and
stays available.
"""


def definitions(feature):
    return (
        feature(
            "platform.help_centre", None, "Help centre",
            "A searchable guide with articles for members, every staff role, organisations, the "
            "superadmin and host operators, and a Help link beside each console screen.",
            default_enabled=True,
        ),
    )
