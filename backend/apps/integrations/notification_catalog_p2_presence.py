"""Presence envelopes have web/push defaults; no room or email delivery."""

from .notification_enums import NotificationChannel as C, NotificationFeature as F


def register(events, defaults):
    events[F.PRESENCE] = ("expired",)
    defaults[F.PRESENCE] = {
        channel: channel in {C.IN_APP, C.NATIVE_PUSH} for channel in C.values
    }
