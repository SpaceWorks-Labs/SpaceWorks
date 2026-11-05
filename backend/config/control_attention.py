"""What needs the superadmin's attention, for the /control/ home (#188).

Each row is a count, a plain label, a link to the list that shows it, and where the web
superadmin console handles the same thing (#190). Rows with nothing to do are left out.
Counts only: no names, addresses or other personal details.
"""

from datetime import timedelta

from django.urls import NoReverseMatch, reverse

STUCK_AFTER = timedelta(minutes=30)
RECENT = timedelta(days=30)


def _link(route, query=""):
    try:
        return reverse(route) + query
    except NoReverseMatch:  # the app is tombstoned on this deployment
        return None


def _stuck_outbox(now):
    from apps.integrations.models_contract import NotificationDelivery, NotificationEnvelope
    from apps.integrations.models_email import EmailLog

    before = now - STUCK_AFTER
    return (EmailLog.objects.filter(status__in=("pending", "sending"), created_at__lt=before).count()
            + NotificationEnvelope.objects.filter(processed_at__isnull=True, created_at__lt=before).count()
            + NotificationDelivery.objects.filter(state="retrying", created_at__lt=before).count())


def _optional(app_label, count):
    from apps.separability.registry import runtime_active

    return count() if runtime_active(app_label) else 0


def _rows(now):
    from apps.accounts.models_ip_access import IPAutoBlock
    from apps.apiclients.models import ApiKeyRequest
    from apps.backup.models import BackupArchive
    from apps.backup.models_drill import RestoreDrillReport
    from apps.hosting_requests.models import HostingRequest
    from apps.makerspaces.models import MakerspaceArchiveRequest, SubdomainRequest
    from apps.space_controls.models import SpaceControlState

    controls = SpaceControlState.objects.all()

    def moves():
        from apps.tenant_migration.models_selfhost_move import SelfHostMoveRequest
        return SelfHostMoveRequest.objects.filter(status="requested").count()

    return (
        ("Hosting requests waiting for review", HostingRequest.objects.filter(status="submitted").count(),
         "admin:hosting_requests_hostingrequest_changelist", "?status__exact=submitted", "Platform → Spaces → Onboarding"),
        ("Archive requests waiting", MakerspaceArchiveRequest.objects.filter(status="pending").count(),
         "admin:makerspaces_makerspacearchiverequest_changelist", "?status__exact=pending", "Platform → Spaces → Health"),
        ("Spaces scheduled to be archived or purged",
         controls.filter(archive_on__isnull=False).count() + controls.filter(purge_due_at__isnull=False).count(),
         "admin:space_controls_spacecontrolstate_changelist", "", "Platform → Spaces → Health"),
        ("Paused spaces", controls.filter(suspended_at__isnull=False).count(),
         "admin:space_controls_spacecontrolstate_changelist", "", "Platform → Spaces → Health"),
        ("Read-only spaces", controls.filter(read_only_at__isnull=False).count(),
         "admin:space_controls_spacecontrolstate_changelist", "", "Platform → Spaces → Health"),
        ("Restore drills failed in the last 30 days",
         RestoreDrillReport.objects.filter(outcome="failed", started_at__gte=now - RECENT).count(),
         "admin:backup_restoredrillreport_changelist", "?outcome__exact=failed", "Platform settings → Restore drills"),
        ("Backups failed in the last 30 days",
         BackupArchive.objects.filter(status="failed", created_at__gte=now - RECENT).count(),
         "admin:backup_backuparchive_changelist", "", "a space's Backups page"),
        ("Networks blocked now", IPAutoBlock.objects.filter(blocked_until__gt=now).count(),
         "admin:accounts_ipautoblock_changelist", "", "Platform settings → IP access"),
        ("Messages stuck for more than 30 minutes", _stuck_outbox(now),
         "admin:integrations_emaillog_changelist", "?status__exact=pending", "Platform → Analytics (outbox health)"),
        ("Self-host move requests waiting", _optional("tenant_migration", moves),
         "admin:tenant_migration_selfhostmoverequest_changelist", "?status__exact=requested", "Platform settings → Self-host moves"),
        ("API key requests waiting", ApiKeyRequest.objects.filter(status="pending").count(),
         "admin:apiclients_apikeyrequest_changelist", "?status__exact=pending", "a space's API clients page"),
        ("Web address requests waiting", SubdomainRequest.objects.filter(status="pending").count(),
         "admin:makerspaces_subdomainrequest_changelist", "?status__exact=pending", "a space's Settings → Domain"),
    )


def attention_items(now):
    items = []
    for label, count, route, query, console in _rows(now):
        if count:
            items.append({"label": label, "count": count, "link": _link(route, query), "console": console})
    return items
