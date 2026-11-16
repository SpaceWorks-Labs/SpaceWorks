"""Approved row-owned app identities shared by mobile integration tests."""

from apps.accounts.models import NativeAppRegistration

APP = "org.spaceworks.app"
FIRST = "ab" * 32
SECOND = "cd" * 32
PREFIX = "TEAMID1234"


def registration(platform="android", **overrides):
    values = {
        "platform": platform, "app_id": APP, "environment": "production",
        "makerspace": None, "status": NativeAppRegistration.Status.APPROVED,
        "verifier_config_key": APP,
        "signing_identities": [PREFIX] if platform == "apple" else [FIRST, SECOND],
    }
    values.update(overrides)
    identity = {key: values.pop(key) for key in ("platform", "app_id", "environment", "makerspace")}
    row, _ = NativeAppRegistration.objects.update_or_create(**identity, defaults=values)
    return row
