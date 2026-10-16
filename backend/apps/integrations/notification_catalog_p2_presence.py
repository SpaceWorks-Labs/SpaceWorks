"""Presence envelopes have web/push defaults; no room or email delivery."""


def register(events, defaults):
    events["presence"] = ("expired",)
    defaults["presence"] = {"in_app": True, "native_push": True}
