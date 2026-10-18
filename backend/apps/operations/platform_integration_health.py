"""Read-only channel health for monitoring; never bootstrap platform settings."""

from apps.integrations.health import (
    _destinations_section, _email_section, _safe_section, _telegram_section,
)


def _smtp_snapshot(space):
    from apps.integrations.models import PlatformEmailSettings
    from apps.integrations.mail_providers.selection import stored_config, environment_config
    if stored_config(space, tenant=True) is not None:
        return {"status": "ok", "configured": True}
    row = PlatformEmailSettings.objects.filter(pk=1).first()
    selected = stored_config(row) if row else None
    return {"status": "ok", "configured": selected is not None or environment_config() is not None}


def integration_snapshot(space):
    # The general integration-health builder also reads SMS/push configuration via
    # load(), which creates singleton rows. Only these four sections are needed.
    return {
        "email": _safe_section(lambda: _email_section(space)),
        "smtp": _safe_section(lambda: _smtp_snapshot(space)),
        "telegram": _safe_section(lambda: _telegram_section(space)),
        "chat_destinations": _safe_section(lambda: _destinations_section(space)),
    }
