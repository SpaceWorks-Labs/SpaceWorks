"""How each module's rows are actually removed (plan A9).

One function per module, called from `module_purge_plans.PLANS` inside the purge
transaction, after the caller has opened the transaction-scoped immutability bypass.
Splitting these out of the plan registry keeps "which plans exist" readable next to
"what each one deletes", and keeps both files inside the file-size ceiling.

Two rules every collector here obeys:

* **Only what this module owns.** The makerspace survives the purge and other modules
  stay installed, so a collector must not reach into their rows -- see
  `machine_service_delete`, which is deliberately narrower than the whole-tenant
  `machines.service_lifecycle.delete_for_makerspace`.
* **Model imports are function-local.** This module is imported by the plan registry,
  which the management command imports at load time; importing app models at module
  scope would drag half the app graph into every `manage.py` invocation.
"""
from apps.makerspaces.module_purge_collectors_machine_service import machine_service_delete
from apps.makerspaces.module_purge_collectors_membership import (
    membership_delete,
    membership_private_key_sizes,
    membership_private_keys,
    membership_public_image_keys,
)
from apps.makerspaces.module_purge_collectors_single_model import (
    _counts,
    _delete,
    bookings_delete,
    bookings_public_images,
    machine_service_private_key_sizes,
    machine_service_private_keys,
    qr_print_batches_delete,
    stock_transfers_delete,
    stocktake_delete,
)


from .module_purge_collectors_events import (
    events_delete, events_public_images, events_private_keys, events_private_key_sizes,
)


def maintenance_delete(makerspace, cursor):
    from apps.maintenance.models import (
        MaintenanceLog,
        MaintenanceLogDocument,
        MaintenanceSchedule,
        MaintenanceCalendarFeed,
    )
    documents, document_labels = _delete(
        MaintenanceLogDocument.objects.filter(log__machine__makerspace=makerspace)
    )
    logs, log_labels = _delete(
        MaintenanceLog.objects.filter(machine__makerspace=makerspace)
    )
    schedules, schedule_labels = _delete(
        MaintenanceSchedule.objects.filter(machine__makerspace=makerspace)
    )
    feeds, feed_labels = _delete(MaintenanceCalendarFeed.objects.filter(makerspace=makerspace))
    return _counts(
        model_labels=document_labels | log_labels | schedule_labels | feed_labels,
        calendar_feeds=feeds,
        documents=documents,
        logs=logs,
        schedules=schedules,
    )


def maintenance_private_keys(makerspace, add):
    from apps.maintenance.models import MaintenanceLogDocument

    for key in MaintenanceLogDocument.objects.filter(
        log__machine__makerspace=makerspace
    ).values_list("object_key", flat=True):
        add(key)


def maintenance_private_key_sizes(makerspace):
    """Charged bytes per document key, for release after a confirmed object delete.

    `services_documents.upload_log_document` charges `limits.add_storage`, so purging the
    module must give those bytes back -- but only for objects the bucket confirms are
    gone. Freeing them alongside the row deletion looked safe because the size comes from
    a column rather than an S3 HEAD, and it is not: the rows commit, the best-effort
    object delete can then fail, and the makerspace ends up holding storage it is no
    longer charged for.
    """
    from apps.maintenance.models import MaintenanceLogDocument

    return {
        key: size
        for key, size in MaintenanceLogDocument.objects.filter(
            log__machine__makerspace=makerspace
        ).values_list("object_key", "size_bytes")
        if key
    }


def notifications_delete(makerspace, cursor):
    from apps.accounts import rbac
    from apps.notifications.models import Notification, NotificationInboxRow, MemberBroadcast
    # Inbox retention cannot revoke channel proofs/preferences or destroy an
    # envelope needed for email, SMS, WhatsApp or native push without an inbox.
    deleted, labels = 0, []
    for model in (NotificationInboxRow, Notification, MemberBroadcast):
        count, model_labels = _delete(rbac.scope_notification_policy(
            model.objects.all(), makerspace_id=makerspace.pk,
        ))
        deleted += count
        labels.extend(model_labels)
    return _counts(model_labels=labels, notifications=deleted)


def _chat_destinations_delete(makerspace, channel):
    """Delete one chat channel's rooms and their stored credentials.

    This was not needed while a channel's credential was a column on `Makerspace` — the
    channel owned no rows at all. A destination holds an encrypted webhook URL or chat id,
    so purging `discord` after uninstalling it must destroy those secrets, not leave them
    readable in a table nothing surfaces any more. The scope link tables and the delivery
    logs' `destination` FK both fall out of this by CASCADE and SET_NULL respectively:
    history survives, the credential does not.
    """
    from apps.integrations.models_destinations import NotificationDestination
    from apps.integrations.models_endpoints import ChannelConfiguration

    ChannelConfiguration.objects.filter(makerspace=makerspace, channel=channel).delete()

    deleted, labels = _delete(
        NotificationDestination.objects.filter(makerspace=makerspace, channel=channel)
    )
    return _counts(model_labels=labels, destinations=deleted)


def telegram_destinations_delete(makerspace, cursor):
    return _chat_destinations_delete(makerspace, "telegram")


def slack_destinations_delete(makerspace, cursor):
    return _chat_destinations_delete(makerspace, "slack")


def mattermost_destinations_delete(makerspace, cursor):
    return _chat_destinations_delete(makerspace, "mattermost")


def discord_destinations_delete(makerspace, cursor):
    return _chat_destinations_delete(makerspace, "discord")


def webhook_destinations_delete(makerspace, cursor):
    return _chat_destinations_delete(makerspace, "webhook")
