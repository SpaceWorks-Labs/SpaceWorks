"""Display consent is independent of profile publication consent."""
from apps.audit import services as audit
from apps.tenant_migration.gate_runtime import tenant_write
from .models import PresencePreference, PresenceSession, PresenceSettings
from .policy import require_account, require_staff


def settings_for(space):
    # Reads must remain reads (including while the tenant is frozen).
    from uuid import UUID
    return PresenceSettings.objects.filter(makerspace=space).first() or PresenceSettings(makerspace=space, display_version=UUID(int=0))


def update_settings(actor, space, values):
    with tenant_write(space.pk):
        require_staff(actor, space, settings=True)
        row, _ = PresenceSettings.objects.get_or_create(makerspace=space)
        row = PresenceSettings.objects.select_for_update().get(pk=row.pk)
        for field in ("show_names", "allow_personal_opt_out"):
            if field in values:
                setattr(row, field, values[field])
        row.save(update_fields=["show_names", "allow_personal_opt_out"])
        audit.record(actor, "presence.settings_updated", makerspace=space, target=row)
        return row


def update_preference(account, space, hide_on_display):
    from .services import _lock_account
    with tenant_write(space.pk):
        require_account(account, space)
        account, space = _lock_account(account, space)
        row, _ = PresencePreference.objects.update_or_create(
            account=account, makerspace=space, defaults={"hide_on_display": hide_on_display})
        # Save each current row so the same transactional cache invalidation runs.
        for session in PresenceSession.objects.select_for_update().filter(
                account=account, makerspace=space, ended_at=None):
            session.hide_on_display = hide_on_display
            session.save(update_fields=["hide_on_display"])
        audit.record(account, "presence.preference_updated", makerspace=space, target=row)
        return row
