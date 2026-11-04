"""Fresh installs start with notification sending allowed; upgrades stay held.

A database holding no prior deployment data has nothing to reconcile, so it is
activated here instead of waiting for `notification_cutover activate`. Every other
database keeps the receipt_only / sending-disabled gate exactly as 0041-0042 left it.
"""
import logging

from django.conf import settings
from django.db import migrations
from django.utils import timezone

logger = logging.getLogger("apps.integrations.notification_cutover")

# Integrations-owned send/receipt history. Any row means this is not a fresh install.
HISTORY_MODELS = (
    "NotificationEnvelope", "NotificationDelivery", "NotificationIngress", "NotificationLegacyMapping",
    "NotificationDeliveryLog", "MessagingDelivery", "MessagingWebhookEvent", "PushDeliveryAttempt",
    "SmsSendLog", "EmailLog", "EmailProviderEvent",
)


def _exists(registry, alias, app_label, name):
    try:
        model = registry.get_model(app_label, name)
    except LookupError:
        return False
    return model.objects.using(alias).exists()


def is_fresh(registry, alias):
    """Narrow test: no makerspace, at most one superuser account, no notification history."""
    if _exists(registry, alias, "makerspaces", "Makerspace"):
        return False
    User = registry.get_model("accounts", "User")
    users = list(User.objects.using(alias).values_list("is_superuser", flat=True)[:2])
    if len(users) > 1 or (users and not users[0]):
        return False
    return not any(_exists(registry, alias, "integrations", name) for name in HISTORY_MODELS)


def decide(registry, schema_editor):
    alias = schema_editor.connection.alias
    Gate = registry.get_model("integrations", "NotificationCutover")
    gate, _ = Gate.objects.using(alias).get_or_create(pk=1)
    if gate.activated_at or gate.reconciled_at:
        return
    pristine = gate.route == "receipt_only" and not gate.sending_enabled and not gate.snapshot.get("_copy_started")
    if not (pristine and is_fresh(registry, alias)):
        gate.snapshot["_install_branch"] = "upgrade_held"
        gate.save(using=alias, update_fields=["snapshot"])
        logger.info("notification_cutover_install_branch", extra={"branch": "upgrade_held"})
        return
    now = timezone.now()
    gate.route, gate.sending_enabled = "canonical", True
    gate.barrier_at = gate.barrier_at or now
    gate.copied_at = gate.copied_at or now
    gate.reconciled_at = gate.activated_at = now
    gate.snapshot["_install_branch"] = "fresh_install_active"
    gate.save(using=alias)
    logger.info("notification_cutover_install_branch", extra={"branch": "fresh_install_active"})


class Migration(migrations.Migration):
    dependencies = [
        ("integrations", "0045_addressed_channels_survive_inbox_removal"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [migrations.RunPython(decide, migrations.RunPython.noop)]
