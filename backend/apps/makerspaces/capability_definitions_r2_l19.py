"""Release-2 lane L19: watch-friendly native push actions (#116, #128 C-27).

`mobile.watch_actions` is ON by default (C-27). While on, a native push carries a safe
action set (`category`): Open, Mark seen, and Snooze while `notifications.inbox_snooze` is
on. Each action only opens the app or calls the person's own inbox routes; money and
evidence notices never get one. Off: pushes still arrive, without action buttons.

It does not declare `requires_features=("mobile.push",)`: no push is sent while push is off,
so the AND is implicit, and a declared requirement would make switching push off fail
validation in every space that keeps this default-on switch.
"""


def definitions(feature):
    return (
        feature(
            "mobile.watch_actions", "mobile", "Watch-friendly push actions",
            "Open and Mark seen buttons (plus Snooze when inbox snooze is on) on phone and watch "
            "notifications. Never money, evidence, approval or handover actions.",
            default_enabled=True,
        ),
    )
