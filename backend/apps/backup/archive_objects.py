"""Legacy object collection plus immutable object-byte capture."""

from django.apps import apps
from django.conf import settings

from apps.backup import storage
from apps.data_export.datasets import DATASET_SPECS
from .capture_managers import every_row


OBJECT_FIELD_NAMES = frozenset({
    "object_key", "image_key", "avatar_key", "cover_image_key", "copy_key",
    "logo_key",
    "photo_object_key",
    "branding_logo_key",
    "staging_key", "verification_key",
})

NON_OBJECT_KEY_FIELDS = frozenset({
    # Sender/correlation identities are protected provider state, never S3 keys.
    ("integrations.MakerspaceMessagingSettings", "sms_sender_key"),
    ("integrations.MakerspaceMessagingSettings", "whatsapp_sender_key"),
    ("integrations.MessagingDelivery", "event_key"),
    ("integrations.MessagingDelivery", "sender_key"),
    ("integrations.MessagingRecipientAlias", "sender_key"),
    ("integrations.MessagingRecipientCorrelation", "sender_key"),
    ("integrations.MessagingSenderIdentity", "sender_key"),
    ("integrations.MessagingSuppression", "sender_key"),
    ("integrations.MessagingWebhookEvent", "sender_key"),
    # Canonical cutover sender bindings and receipt dedupe identities are provider
    # correlation strings (deployment-local), never bucket locators.
    ("integrations.ChannelConfiguration", "sender_key"),
    ("integrations.MessagingConsent", "sender_key"),
    ("integrations.NotificationCredentialVersion", "sender_key"),
    ("integrations.NotificationDelivery", "sender_key"),
    ("integrations.NotificationIngress", "dedupe_key"),
    ("integrations.NotificationIngress", "sender_key"),
    ("integrations.NotificationProviderReference", "sender_key"),
    ("operations.CloudEmailReservation", "attempt_key"),  # stable mail replay identity
    ("operations.CloudObjectUsageReceipt", "operation_key"),  # accounting idempotency, no object locator
    # Replay-receipt digest of tenant, provider and event id, not a locator.
    ("integrations.EmailProviderWebhookReceipt", "event_key"),
    # Notification intent and delivery-target identities, never bucket locators.
    ("integrations.NotificationEnvelope", "dedup_key"),
    ("integrations.NotificationDelivery", "target_key"),
    # UUID identifying one inbox fan-out, never a bucket locator.
    ("notifications.NotificationInboxRow", "event_key"),
    # UUID of the notification an escalation follows (L2), never a bucket locator.
    ("notifications.NotificationEscalation", "event_key"),
    # Name of the module setting a Space Manager locked (L17), never a bucket locator.
    ("makerspaces.ModuleSettingLock", "setting_key"),
    ("accounts.NativeAppRegistration", "verifier_config_key"),
    # App Attest credential PEM, never an object-storage locator.
    ("accounts.DeviceGrant", "attestation_public_key"),
    ("accounts.PlatformSocialAuthSettings", "apple_private_key"),
    ("audit.AuditMacKey", "wrapped_key"),
    ("audit.AuditSigningKey", "public_key"),
    # Base64 of a device's raw Ed25519 public key; a credential, not an object pointer.
    ("devices.Device", "public_key"),
    ("audit.AuditSigningKey", "wrapped_private_key"),
    ("audit.AuditSigningKeyRotation", "new_key"),
    ("audit.AuditSigningKeyRotation", "old_key"),
    ("backup.RestoreRollbackObject", "module_key"),
    # An encrypted offsite-destination credential, not an object pointer.
    ("backup.BackupDestination", "secret_access_key"),
    # Logical identity strings, not object-store pointers: the occurrence key names a
    # position within a recurring series, and the rollup keys name which metric a row
    # holds. Nothing is stored in a bucket for any of them.
    ("events.Event", "series_occurrence_key"),
    # Stage trigger and payee-template selectors are closed vocabulary labels.
    ("events.StageFormAssignment", "trigger_key"),
    ("payments.EventPayeeRevision", "template_key"),
    ("operations.ReportMetricRollup", "dimension_key"),
    ("operations.ReportMetricRollup", "metric_key"),
    ("operations.ReportMetricRollup", "report_key"),
    ("operations.ReportSchedule", "report_key"),
    ("backup.RestoreRollbackObject", "source_key"),
    # Run-owned promotion staging is retry coordination, not durable archive
    # content. The final object and artifact ledger are the restore authority.
    ("backup.BackupArchive", "staging_object_key"),
    ("integrations.PlatformPushSettings", "apns_private_key"),
    ("makerspaces.Makerspace", "public_api_key"),
    ("payments.MakerspacePaymentSettings", "stripe_publishable_key"),
    ("payments.MakerspacePaymentSettings", "stripe_secret_key"),
    ("payments.PlatformStripeConnectSettings", "stripe_publishable_key"),
    ("payments.PlatformStripeConnectSettings", "stripe_secret_key"),
    ("sessions.Session", "session_key"),
    ("tenant_migration.DeploymentSigningKey", "public_key"),
    ("tenant_migration.MigrationPairing", "source_public_key"),
    ("tenant_migration.MigrationPairing", "target_public_key"),
    # Transient staging locator for an exit artifact that was never published.
    # The bytes are deleted on refusal and renamed on publication, so a captured
    # copy would restore as a pointer to something that must not exist.
    ("tenant_migration.TenantDumpCapture", "unpublished_object_key"),
    ("tenant_migration.TenantImportObject", "source_key"),
    ("tenant_migration.TenantImportObject", "target_key"),
    # Events programme logical identifiers: a saved-detail field name, a form identity,
    # a help-request dedup token and an integrity-rule name. None names a bucket object.
    ("accounts.MemberSavedDetail", "field_key"),
    ("events.EventFormRevision", "form_key"),
    ("events.EventHelpRequest", "dedup_key"),
    ("events.SubmissionIntegrityFlag", "rule_key"),
})


def object_closure():
    """Compatibility closure for non-compound makerspace archives."""
    result = {"private": {}, "public_image": {}}
    for model in apps.get_models():
        # Receipt keys are deletion locators for objects that must NOT exist.
        if model._meta.label in {"evidence.EvidenceAbandonedUploadReceipt", "accounts.AccountPurgeObject",
                                  "backup.ManagedStagedObject"}:
            continue
        collect_model_objects(every_row(model).all(), model, result)
    return result


def collect_model_objects(queryset, model, result, fixed_makerspace_id=None):
    if model._meta.label == "accounts.AccountPurgeObject":
        # A deletion journal is never a request to resurrect erased profile bytes.
        return
    # Share the compound archive's field-specific bucket declarations. A public
    # gallery uses object_key too; field spelling alone cannot select its bucket.
    from .object_ownership_registry import FIELD_OBJECT_RULES, ReferencePolicy

    buckets = {(rule.model_label, rule.field_name): rule.bucket.value for rule in FIELD_OBJECT_RULES}
    rules = {(rule.model_label, rule.field_name): rule for rule in FIELD_OBJECT_RULES}
    if model._meta.label in {"events.EventCertificateArtwork", "events.EventCertificateLibraryArtwork"}:
        queryset = queryset.filter(promoted_at__isnull=False)
    spec = DATASET_SPECS.get(model._meta.label)
    ownership_paths = spec[1].any_paths if spec else ()
    if not ownership_paths and any(
        field.name == "makerspace" for field in model._meta.concrete_fields
    ):
        ownership_paths = ("makerspace",)
    for field in model._meta.concrete_fields:
        if field.name not in OBJECT_FIELD_NAMES:
            continue
        rule = rules[(model._meta.label, field.name)]
        if rule.policy == ReferencePolicy.COORDINATION_ONLY:
            continue
        if model._meta.label == "evidence.EvidencePhoto" and field.name == "object_key":
            _collect_evidence_objects(queryset, result, fixed_makerspace_id)
            continue
        from .object_reference_legacy import collect_retained
        if collect_retained(queryset, model, rule, ownership_paths, result, fixed_makerspace_id):
            continue
        if field.name == "copy_key":
            rows = queryset.exclude(copy_key="").values_list(
                "copy_key", "bucket_kind", "makerspace_id", "module_key"
            )
            for key, kind, owner, module_key in rows:
                result[kind][str(key)] = {
                    "makerspace_id": owner, "module_key": module_key,
                }
            continue
        bucket_kind = buckets[(model._meta.label, field.name)]
        value_paths = [
            path if path in {"pk", "id"} else f"{path}_id"
            for path in ownership_paths
        ]
        rows = queryset.exclude(**{field.name: ""}).values_list(
            field.name, *value_paths
        )
        for values in rows:
            key, *owners = values
            if key and not str(key).startswith("backup-archives/"):
                owner = fixed_makerspace_id or next(
                    (item for item in owners if item), None
                )
                result[bucket_kind][str(key)] = {
                    "makerspace_id": owner,
                    "module_key": module_for_model(model._meta.label),
                }


def _collect_evidence_objects(queryset, result, fixed_makerspace_id):
    rows = queryset.exclude(object_key="").values(
        "object_key",
        "makerspace_id",
        "object_retention_state__status",
        "object_retention_state__object_expired_at",
        "object_retention_state__expired_size_bytes",
    )
    for row in rows:
        status = row["object_retention_state__status"]
        if status in {"expiring", "cleaning"}:
            raise storage.BackupStorageError(
                "Evidence expiry is in progress; retry the archive after it completes."
            )
        ownership = {
            "makerspace_id": fixed_makerspace_id or row["makerspace_id"],
            "module_key": "",
        }
        if status == "expired":
            expired_at = row["object_retention_state__object_expired_at"]
            if expired_at is None:
                raise storage.BackupStorageError(
                    "Expired evidence is missing its terminal timestamp."
                )
            ownership.update(
                retention_state="expired",
                object_expired_at=expired_at.isoformat(),
                expired_size_bytes=row[
                    "object_retention_state__expired_size_bytes"
                ],
            )
        result["private"][str(row["object_key"])] = ownership


def capture_objects(root, object_keys, modes):
    from .object_capture_proof import PROOF_FIELDS, assert_capture_proof
    manifest = []
    buckets = {
        "private": settings.AWS_STORAGE_BUCKET_NAME,
        "public_image": settings.PUBLIC_IMAGE_BUCKET,
    }
    for kind, keys in object_keys.items():
        if kind not in buckets:
            raise ValueError(f"Unsupported backup bucket kind: {kind!r}.")
        for key, ownership in sorted(keys.items()):
            if ownership.get("retention_state") == "expired":
                storage.assert_object_absent(buckets[kind], key)
                storage.assert_object_absent(buckets[kind], f"staging/{key}")
                manifest.append(
                    {
                        "bucket_kind": kind,
                        **ownership,
                        "key": key,
                        "version_id": None,
                        "size": 0,
                        "sha256": "",
                        "metadata": {},
                        "content_type": "",
                        "headers": {},
                    }
                )
                continue
            destination = root / kind / key
            item = storage.download_object(
                buckets[kind], key, destination, versioned=modes[kind] == "versioned"
            )
            assert_capture_proof(ownership, item)
            public_facts = {name: value for name, value in ownership.items() if name not in PROOF_FIELDS}
            manifest.append({"bucket_kind": kind, **public_facts, **item})
    return manifest


def module_for_model(label):
    if label.startswith("events."):
        return "events"
    return {
        "events.EventPageAsset": "events",
        "bookings.BookingResourcePageAsset": "bookings",
        "events.Event": "events",
        "events.EventSeries": "events",
        "events.EventAttendanceCertificate": "events",
        "events.EventCertificateArtwork": "events",
        "bookings.BookableSpace": "bookings",
        "bookings.BookableSpacePhoto": "bookings",
        "maintenance.MaintenanceLogDocument": "maintenance",
        "procurement.ToBuyReceipt": "procurement",
        "makerspaces.MemberProfile": "membership",
        "makerspaces.MemberProject": "membership",
        "machines.ServiceRequestFile": "machine_service",
        "operations.ReportDelivery": "reports",
    }.get(label, "")
