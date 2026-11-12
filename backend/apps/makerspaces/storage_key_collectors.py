"""Canonical tenant object-key closure shared by migration and purge."""


def collect_private_object_keys(makerspace, *, include_coordination=True):
    from .models_public_pages import MakerspacePublicPageAsset
    from apps.bookings.models_website import BookingResourcePageAsset
    from apps.evidence.models import EvidencePhoto
    from apps.events.models import EventAttendanceCertificate, EventCertificateArtwork, EventPageAsset
    from apps.maintenance.models import MaintenanceLogDocument
    from apps.machines.models import MachineDocument, MachineTypeDocument
    from apps.machines.service_lifecycle import collect_private_object_keys as collect_service
    from apps.procurement.models import ToBuyReceipt
    from apps.warranty.models import WarrantyDocument

    keys, seen = [], set()

    def add(key):
        if key and key not in seen:
            seen.add(key)
            keys.append(str(key))

    for model, lookup in (
        (EventPageAsset, {"page__makerspace": makerspace}),
        (MakerspacePublicPageAsset, {"page__makerspace": makerspace}),
        (BookingResourcePageAsset, {"page__space__makerspace": makerspace}),
        (EvidencePhoto, {"makerspace": makerspace}),
        (EventAttendanceCertificate, {"event__makerspace": makerspace}),
        (WarrantyDocument, {"warranty__makerspace": makerspace}),
        (ToBuyReceipt, {"to_buy_item__makerspace": makerspace}),
        (MaintenanceLogDocument, {"log__machine__makerspace": makerspace}),
        (MachineDocument, {"machine__makerspace": makerspace}),
        (MachineTypeDocument, {"makerspace": makerspace}),
    ):
        for key in model.objects.filter(**lookup).values_list("object_key", flat=True):
            add(key)
            if model is EvidencePhoto and include_coordination and key:
                from apps.evidence.storage import staging_key
                add(staging_key(key))
    collect_service(makerspace, add)
    from .storage_keys_events_programme import collect_programme_keys
    collect_programme_keys(makerspace, add, include_coordination=include_coordination)
    from .storage_keys_cards import collect_card_keys
    collect_card_keys(makerspace, add, include_coordination=include_coordination)
    from apps.payments.models import PaymentDocument
    for key in PaymentDocument.objects.filter(makerspace=makerspace).values_list("branding_logo_key", flat=True):
        add(key)
    artwork = EventCertificateArtwork.objects.filter(event__makerspace=makerspace)
    if not include_coordination:
        artwork = artwork.filter(promoted_at__isnull=False)
    for key in artwork.values_list("object_key", flat=True):
        add(key)
        if include_coordination:
            add(f"staging/{key}")
    if include_coordination:
        _collect_private_coordination_keys(makerspace, add)
        from django.conf import settings
        if settings.SPACEWORKS_DEPLOYMENT_MODE == "managed" or getattr(settings, "STORAGE_CAPABILITIES_FILE", ""):
            from apps.storage_capabilities.presigning import public_image_staging
            for key in collect_public_image_keys(makerspace, include_coordination=False):
                add(public_image_staging(key, private_bucket=settings.AWS_STORAGE_BUCKET_NAME).key)
    else:
        # Migration capture/verification only; purge keeps its locator-driven deletion.
        from .storage_keys_reimbursements import collect_portable_keys
        collect_portable_keys(makerspace, add)
    return keys


def collect_public_image_keys(makerspace, *, include_coordination=True):
    from apps.bookings.models import BookableSpace
    from apps.events.models import Event, EventSeries
    from apps.inventory.models import InventoryProduct
    from apps.machines.models import Machine
    from apps.makerspaces.models import MemberProfile, MemberProject

    keys = [makerspace.logo_key, makerspace.cover_image_key]
    for model in (BookableSpace, Event, EventSeries, InventoryProduct, Machine):
        keys.extend(
            model.objects.filter(makerspace=makerspace).values_list("image_key", flat=True)
        )
    keys.extend(
        MemberProfile.objects.filter(membership__makerspace=makerspace).values_list(
            "avatar_key", flat=True
        )
    )
    keys.extend(
        MemberProject.objects.filter(
            profile__membership__makerspace=makerspace
        ).values_list("image_key", flat=True)
    )
    from apps.bookings.purge_p2 import photo_keys
    keys.extend(photo_keys(makerspace))
    from apps.payments.models import Sponsor  # release 2 L18: sponsor logos
    keys.extend(Sponsor.objects.filter(makerspace=makerspace).values_list("logo_key", flat=True))
    if include_coordination:
        keys.extend(_public_coordination_keys(makerspace))
    from apps.makerspaces.account_profile_purge import without_account_held

    return [str(key) for key in without_account_held([str(k) for k in dict.fromkeys(keys) if k])]


def _collect_private_coordination_keys(makerspace, add):
    from apps.admin_api.models import BulkImportJob
    from apps.backup.models import RestoreRollbackObject
    from apps.data_export.models import DataExportJob
    from apps.tenant_migration.models import TenantImportObject

    for name in BulkImportJob.objects.filter(makerspace=makerspace).values_list(
        "upload", flat=True
    ):
        add(name)
    for name in DataExportJob.objects.filter(makerspace=makerspace).values_list(
        "object_key", flat=True
    ):
        add(name)
    for key in RestoreRollbackObject.objects.filter(
        makerspace=makerspace,
        bucket_kind=RestoreRollbackObject.BucketKind.PRIVATE,
    ).exclude(copy_key="").values_list("copy_key", flat=True):
        add(key)
    # Purge deletes both receipt keys immediately but never the FK-free receipt itself,
    # which keeps repairing a late upload after the tenant row is gone.
    from apps.evidence.models import EvidenceAbandonedUploadReceipt
    from apps.evidence.storage import staging_key as evidence_staging_key

    for key in EvidenceAbandonedUploadReceipt.objects.filter(
        source_makerspace_id_snapshot=makerspace.pk
    ).values_list("object_key", flat=True):
        add(key)
        add(evidence_staging_key(key))
    objects = TenantImportObject.objects.filter(job__target_makerspace=makerspace)
    for staging_key in objects.exclude(staging_key="").values_list(
        "staging_key", flat=True
    ):
        add(staging_key)
    for target_key in objects.filter(
        bucket_kind=TenantImportObject.BucketKind.PRIVATE
    ).exclude(target_key="").values_list("target_key", flat=True):
        add(target_key)


def _public_coordination_keys(makerspace):
    from apps.accounts.models_account_purge import AccountPurgeObject
    from apps.backup.models import RestoreRollbackObject
    from apps.tenant_migration.models import TenantImportObject

    keys = list(
        RestoreRollbackObject.objects.filter(
            makerspace=makerspace,
            bucket_kind=RestoreRollbackObject.BucketKind.PUBLIC_IMAGE,
        ).exclude(copy_key="").values_list("copy_key", flat=True)
    )
    keys.extend(
        TenantImportObject.objects.filter(
            job__target_makerspace=makerspace,
            bucket_kind=TenantImportObject.BucketKind.PUBLIC_IMAGE,
        ).exclude(target_key="").values_list("target_key", flat=True)
    )
    # Profiles may already be gone while durable account image deletion retries.
    # Break-glass tenant purge must still collect those source-only keys.
    keys.extend(AccountPurgeObject.objects.filter(makerspace=makerspace, deleted_at__isnull=True)
                .values_list("object_key", flat=True))
    return keys
