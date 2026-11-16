"""Account-PK cleanup for optional inbox and inbox-independent push history.

M calls scrub_account from its canonical privacy seam while the caller holds the
cutover -> sorted tenant -> User lifecycle locks. No contact-address matching.
"""
from django.db import transaction
from django.db.models import Q

from apps.integrations.notification_cutover import guarded
from apps.notifications.models_inbox import NotificationInboxRow
from apps.notifications.models_push import MemberPushDelivery


@guarded(mutation=True)
@transaction.atomic
def scrub_account(user, makerspace_id=None, *, purge=False):
    scope = {"envelope_delivery__makerspace_id": makerspace_id} if makerspace_id is not None else {}
    owned = MemberPushDelivery.objects.filter(
        Q(envelope_delivery__envelope__recipient_id=user.pk) | Q(inbox_row__user_id=user.pk), **scope,
    )
    # Keep status predicates on the updated table, outside the ownership subquery:
    # Postgres must recheck them if a fenced provider completion wins a row lock.
    children = MemberPushDelivery.objects.filter(pk__in=owned.values("pk"))
    from apps.integrations.models_cutover import NotificationLegacyMapping
    from apps.integrations.models_contract import NotificationEnvelope
    history_scope = {"makerspace_id": makerspace_id} if makerspace_id is not None else {}
    old_ids = [int(identity) for identity in NotificationEnvelope.objects.filter(
        recipient_id=user.pk, source_kind="migration.history", context__legacy_model="MemberPushDelivery",
        **history_scope,
    ).values_list("source_id", flat=True) if identity.isascii() and identity.isdecimal()]
    # The device may already have cascaded away; its inert parent still proves
    # ownership of the original mapping without guessing from contact fields.
    mappings = NotificationLegacyMapping.objects.filter(legacy_model="MemberPushDelivery").filter(
        Q(legacy_id__in=children.values("pk")) | Q(legacy_id__in=old_ids),
    )
    mappings.update(snapshot="")
    # Fence completions before deleting or redacting any private rows. Preserve
    # terminal outcome telemetry during archive; nothing can revive on restore.
    children.exclude(status__in=["sent", "failed", "skipped", "canceled"]).update(
        status="canceled", retryable=False, lease_token=None, lease_until=None,
        last_error="account_removed",
    )
    children.filter(status="failed").update(retryable=False)
    inbox_scope = {"makerspace_id": makerspace_id} if makerspace_id is not None else {}
    inbox = NotificationInboxRow.objects.filter(user_id=user.pk, **inbox_scope)
    if purge:
        children.delete()
        inbox.delete()
    else:
        # Save rewrites encrypted title/summary in their tenant scope.
        for row in inbox.select_for_update().iterator():
            row.title, row.summary, row.link, row.scope = "", "", "", {}
            row.save(update_fields=["title", "summary", "link", "scope"])
