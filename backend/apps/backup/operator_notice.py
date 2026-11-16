"""Platform-email notices to the superadmins (release 2 L11; #128 C-24).

* "Archive ready" is OPTIONAL and off by default (``archive_ready_notice_enabled``). It
  is sent for a whole-platform archive and for an on-demand "Back up now" archive, never
  for nightly one-space, safety or extracted restore points. It carries a SIGNED
  /control/ link that only opens the archive's page for a signed-in superadmin: never
  the file, never an attachment, never a download bearer. Spaces get no backup email.
* A failed restore drill and a new self-host move request always notify.

Platform mail goes through the platform connection on the governance stream; a delivery
failure is logged and swallowed, never raised into the backup, drill or request flow.
"""
import logging

from django.core import signing
from django.db import transaction
from django.urls import reverse

from apps.audit import services as audit

logger = logging.getLogger(__name__)
SALT = "backup.archive_ready_notice"
LINK_MAX_AGE = 7 * 24 * 3600


def superadmin_emails():
    from apps.accounts.models import User
    return [email.strip() for email in User.objects.filter(
        is_active=True, is_superuser=True, access_status=User.AccessStatus.ACTIVE,
    ).exclude(email="").values_list("email", flat=True) if email.strip()]


def notify_superadmins(subject, text, *, event):
    from apps.integrations.dispatch import dispatch_email
    sent = 0
    for email in superadmin_emails():
        try:
            dispatch_email(to_email=email, subject=subject, text_body=text, makerspace=None,
                           connection="platform", stream="governance", event=event, audience="superadmin",
                           persist_body=False, sync=True)
            sent += 1
        except Exception:  # no exception text: provider errors can carry addresses
            logger.warning(f"{event}_failed")
    return sent


def _base_url():
    from django.conf import settings
    return (getattr(settings, "PUBLIC_APP_BASE_URL", "") or "").rstrip("/")


def archive_link(archive):
    token = signing.dumps({"archive": str(archive.pk)}, salt=SALT)
    return _base_url() + reverse("admin:backup_backuparchive_notice", args=[token])


def archive_from_token(token):
    try:
        return signing.loads(token, salt=SALT, max_age=LINK_MAX_AGE)["archive"]
    except (signing.BadSignature, KeyError, TypeError):
        return None


def notify_archive_ready(archive):
    try:
        return _archive_ready(archive)
    except Exception:  # an optional notice never fails the backup that triggered it
        logger.warning("backup_archive_ready_notice_failed")
        return 0


def _archive_ready(archive):
    from .models import BackupArchive, PlatformBackupSettings
    if not PlatformBackupSettings.load().archive_ready_notice_enabled:
        return 0
    if archive.status != BackupArchive.Status.AVAILABLE or not (
            archive.scope == BackupArchive.Scope.DEPLOYMENT or archive.trigger == BackupArchive.Trigger.ON_DEMAND):
        return 0
    where = archive.makerspace.name if archive.makerspace_id else "the whole platform"
    text = (f"A backup of {where} is ready. It is encrypted to the platform key and stays on the server.\n\n"
            f"Open it in the control plane (you will be asked to sign in): {archive_link(archive)}\n\n"
            "This link opens the archive's page only; it never downloads the file.")
    sent = notify_superadmins("Backup archive ready", text, event="backup_archive_ready")
    audit.record(None, "backup.operator_notice_sent", makerspace=archive.makerspace, target=archive,
                 meta={"notice": "archive_ready", "scope": archive.scope, "recipients": sent})
    return sent


def notify_drill_failed(report):
    path = reverse("admin:backup_restoredrillreport_change", args=[report.pk])
    text = (f"A scheduled restore drill failed ({report.error_code}). The live server was not touched.\n\n"
            f"Review the drill report: {_base_url()}{path}")
    transaction.on_commit(lambda: notify_superadmins("Restore drill failed", text, event="backup_drill_failed"))
