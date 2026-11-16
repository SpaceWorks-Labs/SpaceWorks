"""Frozen historical-model copy helper. No runtime dispatch/proof services are called."""
import hashlib
import json

from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.utils import timezone

from apps.makerspaces.secrets import decrypt_value, encrypt_value


def rowsnapshot(row):
    return encrypt_value(json.dumps({f.attname: getattr(row, f.attname) for f in row._meta.concrete_fields},
        cls=DjangoJSONEncoder, sort_keys=True))


def remember(registry, alias, name, old, target, disposition):
    registry.get_model("integrations", "NotificationLegacyMapping").objects.using(alias).get_or_create(
        legacy_model=name, legacy_id=old.pk, defaults={"canonical_model": target._meta.object_name,
            "canonical_id": target.pk, "makerspace_id": getattr(old, "makerspace_id", None),
            "disposition": disposition, "snapshot": rowsnapshot(old)})


def model(registry, name):
    return registry.get_model("integrations", name)


def settings(registry, alias):
    Config = model(registry, "ChannelConfiguration")
    for old in model(registry, "MakerspaceMessagingSettings").objects.using(alias).order_by("pk").iterator():
        with transaction.atomic(using=alias):
            for channel in ("sms", "whatsapp"):
                try:
                    values = ({"account_sid": old.sms_account_sid, "auth_token": decrypt_value(old.sms_auth_token) if old.sms_auth_token else "",
                        "from_number": old.sms_from_number} if channel == "sms" else {
                        "phone_number_id": old.whatsapp_phone_number_id, "business_account_id": old.whatsapp_business_account_id,
                        "access_token": decrypt_value(old.whatsapp_access_token) if old.whatsapp_access_token else "",
                        "app_secret": decrypt_value(old.whatsapp_app_secret) if old.whatsapp_app_secret else "",
                        "webhook_verify_token": old.whatsapp_webhook_verify_token})
                    own_fields = ("account_sid", "auth_token", "from_number") if channel == "sms" else (
                        "phone_number_id", "business_account_id", "access_token", "app_secret")
                    if not any(values.get(name) for name in own_fields):
                        values = {}  # A generated verify token alone is not an own installation.
                except Exception:
                    # The original encrypted material remains in the immutable mapping.
                    values = {"unreadable_legacy_credentials": "reconfiguration_required"}
                # Never transfer O enabled authority. T installations remain the foundation.
                config, created = Config.objects.using(alias).get_or_create(makerspace_id=old.makerspace_id,
                    channel=channel, defaults={"provider": "twilio" if channel == "sms" else "meta",
                        "enabled": False, "personal_enabled": False, "activation_hold": True,
                        "use_platform_sender": old.use_platform_sender,
                        "credentials": encrypt_value(json.dumps(values)) if values else "",
                        "sender_key": getattr(old, channel + "_sender_key") or ""})
                remember(registry, alias, "MakerspaceMessagingSettings." + channel, old, config,
                    "disabled_import" if created else "alternative_history")


def canonical_snapshots(registry, alias):
    Config, Version = model(registry, "ChannelConfiguration"), model(registry, "NotificationCredentialVersion")
    baseline = model(registry, "NotificationCutover").objects.using(alias).get(pk=1).snapshot
    for config in Config.objects.using(alias).filter(pk__lte=baseline.get("ChannelConfiguration", {}).get("max_id", 0)).iterator():
        with transaction.atomic(using=alias):
            remember(registry, alias, "ChannelConfiguration.T", config, config, "canonical_foundation")
    for config in Config.objects.using(alias).filter(channel__in=["sms", "whatsapp"]).iterator():
        with transaction.atomic(using=alias):
            values = {}
            try:
                values = json.loads(decrypt_value(config.credentials)) if config.credentials else {}
                if config.provider == "meta":
                    key = f"meta:{values['business_account_id']}:{values['phone_number_id']}"
                elif config.channel == "sms":
                    key = f"twilio:{values['account_sid']}:{values['from_number']}"
                else:
                    key = f"twilio-wa:{values['account_sid']}:{values.get('whatsapp_sender') or values['messaging_service_sid']}"
                config.sender_key = key
            except Exception:
                config.activation_hold = True
            config.credentials = encrypt_value(config.credentials) if config.credentials else ""
            from ._notification_sender_conversion_v1 import reserve
            reserve(registry, alias, config, values)
            config.credential_version = config.generation
            config.save(using=alias, update_fields=["sender_key", "credential_version", "activation_hold", "credentials"])
            Version.objects.using(alias).get_or_create(configuration=config, generation=config.generation,
                defaults={"provider": config.provider, "sender_key": config.sender_key,
                    "configuration_reference": config.pk, "makerspace_reference": config.makerspace_id,
                    "integration_identity": config.integration_identity, "credentials": config.credentials})
    Delivery = model(registry, "NotificationDelivery")
    for row in Delivery.objects.using(alias).filter(pk__lte=baseline.get("NotificationDelivery", {}).get("max_id", 0)).iterator():
        with transaction.atomic(using=alias):
            remember(registry, alias, "NotificationDelivery.T", row, row, "canonical_foundation")
    for row in Delivery.objects.using(alias).exclude(historical=True).iterator():
        with transaction.atomic(using=alias):
            if row.attempt_count and (row.state == "retrying" or row.claim_until or row.retryable):
                row.state, row.retryable, row.last_error = "held", False, "migration_unknown_outcome"
                row.claim_until, row.next_attempt_at = None, None
            config = Config.objects.using(alias).filter(makerspace_id=row.makerspace_id, channel=row.channel,
                generation=row.integration_generation, integration_identity=row.integration_identity).first()
            if config:
                row.sender_key, row.credential_version = config.sender_key, config.credential_version
                row.provider_source = "own" if config.credentials else "platform" if config.use_platform_sender else ""
            row.save(using=alias)
            from ._notification_sender_conversion_v1 import remember_reference
            remember_reference(registry, alias, row)
    Template = model(registry, "WhatsAppTemplate")
    maximum = baseline.get("WhatsAppTemplate", {}).get("max_id", 0)
    for binding in Template.objects.using(alias).filter(pk__lte=maximum).iterator():
        with transaction.atomic(using=alias):
            remember(registry, alias, "WhatsAppTemplate.T", binding, binding, "canonical_foundation")
            if not binding.validation_schema:
                binding.approved, binding.needs_review = False, True
                binding.save(using=alias, update_fields=["approved", "needs_review"])


def deliveries(registry, alias):
    Envelope, Delivery = model(registry, "NotificationEnvelope"), model(registry, "NotificationDelivery")
    Mapping = model(registry, "NotificationLegacyMapping")
    for old in model(registry, "MessagingDelivery").objects.using(alias).order_by("pk").iterator(chunk_size=500):
        with transaction.atomic(using=alias):
            if Mapping.objects.using(alias).filter(legacy_model="MessagingDelivery", legacy_id=old.pk).exists():
                continue
            uncertain = old.status == "sending" or (old.status == "pending" and old.attempts > 0)
            terminal = old.status in {"accepted", "sent", "delivered", "read", "failed", "skipped", "suppressed"}
            state = "held" if uncertain else old.status if terminal and old.status != "suppressed" else "skipped"
            envelope = Envelope.objects.using(alias).create(makerspace_id=old.makerspace_id,
                recipient_id=old.user_id, feature=old.feature, event=old.event, audience=old.audience,
                dedup_key=f"migration:messaging:{old.pk}", source_kind="migration.history", source_id=str(old.pk),
                processed_at=timezone.now(), scope=old.scope, context={})
            Envelope.objects.using(alias).filter(pk=envelope.pk).update(created_at=old.created_at)
            row = Delivery.objects.using(alias).create(envelope=envelope, makerspace_id=old.makerspace_id,
                channel=old.channel, target_key="migration", provider=old.provider, sender_key=old.sender_key,
                provider_source=old.provider_source, provider_id=old.provider_message_id,
                # O has no immutable configuration generation; zero is historical, never current authority.
                historical=True, state=state, attempt_count=old.attempts, retryable=False,
                last_error="migration_unknown_outcome" if uncertain else old.skip_reason or old.error_code or
                    ("migration_cancelled" if not terminal else ""), recipient_phone_hash=old.recipient_phone_hash,
                recipient_alias_hash=old.recipient_alias_hash, estimated_segments=old.estimated_segments,
                billed_segments=old.billed_segments, quota_reserved_at=old.quota_reserved_at,
                **{name: getattr(old, name) for name in ["accepted_at", "sent_at", "delivered_at", "read_at", "failed_at"]})
            Delivery.objects.using(alias).filter(pk=row.pk).update(created_at=old.created_at)
            from ._notification_sender_conversion_v1 import remember_reference
            remember_reference(registry, alias, row)
            remember(registry, alias, "MessagingDelivery", old, row, "held" if uncertain else "historical")
            if old.status in {"pending", "sending"}:
                model(registry, "MessagingDelivery").objects.using(alias).filter(pk=old.pk).update(
                    status="skipped", skip_reason="migration_unknown_outcome" if uncertain else "migration_cancelled",
                    lease_token=None, lease_until=None)


def templates(registry, alias):
    Config, Template = model(registry, "ChannelConfiguration"), model(registry, "WhatsAppTemplate")
    Mapping = model(registry, "NotificationLegacyMapping")
    for old in model(registry, "WhatsAppTemplateBinding").objects.using(alias).order_by("pk").iterator():
        with transaction.atomic(using=alias):
            if Mapping.objects.using(alias).filter(legacy_model="WhatsAppTemplateBinding", legacy_id=old.pk).exists():
                continue
            config = Config.objects.using(alias).filter(makerspace_id=old.makerspace_id, channel="whatsapp").first()
            if config is None:
                # Global alternatives are canonical pending-review templates, never
                # automatically selected by any tenant installation's resolver.
                target, _ = Template.objects.using(alias).get_or_create(configuration=None,
                    provider_identity=old.business_account_id, template_name=old.template_name,
                    locale=old.language, feature=old.feature, event=old.event, audience=old.audience,
                    defaults={"variables": old.parameters, "approved": False, "needs_review": True,
                        "validation_schema": {"body": old.parameters}})
                remember(registry, alias, "WhatsAppTemplateBinding", old, target, "pending_review")
                continue
            target, created = Template.objects.using(alias).get_or_create(configuration=config, event=old.event,
                audience=old.audience, locale=old.language, defaults={"feature": old.feature,
                    "template_name": old.template_name, "variables": old.parameters, "approved": False,
                    "needs_review": True, "provider_identity": old.business_account_id,
                    "validation_schema": {"body": old.parameters}})
            remember(registry, alias, "WhatsAppTemplateBinding", old, target,
                "pending_review" if created else "alternative_history")


def consents(registry, alias):
    # Preserve immutable O evidence. Missing sender/generation/proof is deliberately
    # inert; a fresh current consent is required, never an inferred WhatsApp endpoint.
    for old in model(registry, "MessagingConsent").objects.using(alias).order_by("pk").iterator():
        with transaction.atomic(using=alias):
            remember(registry, alias, "MessagingConsent", old, old, "proof_required" if old.action == "opted_in" else "opted_out")


def receipts(registry, alias):
    Receipt = model(registry, "NotificationIngress")
    for old in model(registry, "MessagingWebhookEvent").objects.using(alias).order_by("pk").iterator():
        with transaction.atomic(using=alias):
            payload = {**old.payload, "kind": old.kind}
            identity = {"id": old.dedupe_id, "payload": {key: value for key, value in payload.items()
                if key not in {"protection_applied", "client_reference", "destination", "proof_code", "correlation_missing", "proof_user_id"}}}
            key = hashlib.sha256(json.dumps(["legacy", old.provider, old.channel, old.sender_key,
                None, 0, identity], sort_keys=True).encode()).hexdigest()
            receipt, _ = Receipt.objects.using(alias).get_or_create(dedupe_key=key, defaults={
                "transport": "legacy", "provider": old.provider, "channel": old.channel,
                "sender_key": old.sender_key, "makerspace_id": old.makerspace_id,
                "makerspace_reference": old.makerspace_id,
                "payload": encrypt_value(json.dumps(payload)),
                # Replay every old receipt, including previously abandoned early callbacks.
                "state": "pending", "protection_applied": old.state == "processed" or bool(old.payload.get("protection_applied"))})
            remember(registry, alias, "MessagingWebhookEvent", old, receipt, "replay_required")


def copy(registry, schema_editor):
    alias = schema_editor.connection.alias
    Gate = model(registry, "NotificationCutover")
    gate, _ = Gate.objects.using(alias).get_or_create(pk=1)
    if gate.copied_at:
        return
    from ._notification_push_snapshot_v1 import snapshot as push_snapshot, empty_snapshot
    push = push_snapshot(schema_editor.connection) or empty_snapshot()
    populated = any(model(registry, name).objects.using(alias).exists() for name in [
        "MakerspaceMessagingSettings", "MessagingDelivery", "MessagingConsent", "WhatsAppTemplateBinding",
        "MessagingWebhookEvent", "ChannelConfiguration", "NotificationDelivery"]) or bool(push and push["count"])
    if populated and (gate.route != "receipt_only" or gate.sending_enabled or not gate.barrier_at):
        raise RuntimeError("0042 requires deployed compatibility ingress, drained old instances and recorded barrier")
    if not populated and not gate.snapshot:
        from ._notification_snapshot_v1 import snapshot as initial_snapshot
        gate.snapshot = initial_snapshot(registry, alias)
        gate.snapshot["_push"] = push
        gate.save(using=alias, update_fields=["snapshot"])
    # Fingerprint comparison uses a frozen copy of the barrier algorithm.
    if populated and not gate.snapshot.get("_copy_started"):
        if push != gate.snapshot.get("_push"):
            raise RuntimeError("Push rows or their schema changed after the cutover barrier")
        for name, expected in gate.snapshot.items():
            if name.startswith("_"):
                continue
            digest, count, last_id = hashlib.sha256(), 0, 0
            for row in model(registry, name).objects.using(alias).order_by("pk").values().iterator(chunk_size=500):
                digest.update(json.dumps(row, cls=DjangoJSONEncoder, sort_keys=True).encode())
                count += 1
                last_id = row["id"]
            if {"count": count, "sha256": digest.hexdigest(), "max_id": last_id} != expected:
                raise RuntimeError("Legacy snapshot changed after the cutover barrier")
        if not gate.snapshot:
            raise RuntimeError("Missing barrier snapshot")
        gate.snapshot["_copy_started"] = True
        gate.save(using=alias, update_fields=["snapshot"])
    from django.db.models import F
    model(registry, "MessagingSenderIdentity").objects.using(alias).filter(tenant_reference=None).update(tenant_reference=F("makerspace_id"))
    settings(registry, alias)
    canonical_snapshots(registry, alias)
    deliveries(registry, alias)
    templates(registry, alias)
    consents(registry, alias)
    receipts(registry, alias)
    gate.copied_at = timezone.now()
    gate.barrier_at = gate.barrier_at or gate.copied_at
    gate.save(using=alias)
