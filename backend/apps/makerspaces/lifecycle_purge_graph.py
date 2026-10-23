"""Authorized whole-tenant deletion graph; callers hold the makerspace lock."""

from django.conf import settings
from django.db import connection
from django.db.models import Q


def _delete_object_graph(makerspace):
    from apps.backup.models import RestoreRollbackObject
    from apps.apiclients.models import ApiClient, ApiKeyRequest
    from apps.accounts.models_devices import (
        DeviceAttestationChallenge,
        DeviceGrant,
        DeviceRefreshFamily,
        DeviceRefreshToken,
        NativeAppRegistration,
    )
    from apps.audit.models import (
        AuditBatch,
        AuditBatchLeaf,
        AuditLog,
        AuditSigningKey,
        AuditSigningKeyRotation,
        AuditSigningKeyRotationEvent,
        AuditVerificationRun,
        AuditVerificationRunEvent,
    )
    from apps.boxes.models import Box, BoxScan, QrCode, QrScanEvent
    from apps.evidence.models import EvidenceObjectRetentionState, EvidencePhoto
    from apps.evidence.models import EvidenceRetentionPolicy, EvidenceUploadFinalization
    from apps.events.models import (
        Event,
        EventAttendanceCertificate,
        EventCheckInEvent,
        EventCollaborator,
        EventFeedbackResponse,
        EventFeedbackSurvey,
        EventAudienceOrganization,
        EventOrganizer,
        EventRegistration,
        EventSeries,
        EventSeriesCollaborator,
        EventStationBinding,
        EventStaffGrant, EventStaffGrantInvite,
    )
    from apps.hardware_requests.models import HardwareRequest, ReplayCommand
    from apps.hardware_requests.models import PublicToolLoan, RequesterAccountability
    from apps.hardware_requests.models import ReturnEvent
    from apps.hardware_requests.asset_link_models import HardwareRequestItemAsset
    from apps.integrations.models import EmailTemplate, MachineTypeEmailTemplate
    from apps.inventory.models import Category, InventoryAsset, InventoryProduct
    from apps.makerspaces.models import MakerspaceMembership, Station, StationCredential
    from apps.operations.models import InventoryAdjustment, QrPrintBatch
    from apps.operations.models import StocktakeSession, StockTransfer
    from apps.organizations.models import OrganizationMakerspace
    from apps.machines.models import Machine, MachineType, MakerspaceMachineTypePricing, MakerspaceMachineTypePolicy
    from apps.machines.service_lifecycle import delete_for_makerspace
    from apps.payments.models import Payment, ProcessedStripeEvent, Refund, RefundCase
    from apps.tenant_migration.models import ExternalTenantReference, TenantImportJob

    with connection.cursor() as cursor:
        ReplayCommand.objects.filter(makerspace=makerspace).update(
            predecessor=None, replacement_command=None, resolution_code=None, resolved_by=None, resolved_at=None,
        )
        ReplayCommand.objects.filter(makerspace=makerspace).delete()
        # Suspend triggers for this transaction only. Postgres resets the setting
        # on commit/rollback, so a crash cannot leave immutability triggers disabled.
        # ALTER TABLE DISABLE TRIGGER cannot be re-enabled after modifying the table
        # in the same transaction ("pending trigger events"); a post-commit re-enable
        # would not be crash-safe. Django performs CASCADE/SET_NULL fixups in Python,
        # and the comprehensive purge test asserts that no orphans survive.
        if settings.MANAGED_POSTGRES:
            # Managed Postgres (e.g. Supabase) forbids session_replication_role (needs
            # superuser). Use a custom transaction-scoped GUC that our immutability
            # triggers honor to allow DELETE only; FK triggers stay ON (Django collects
            # the graph in dependency order). Auto-resets on commit/rollback.
            cursor.execute("SET LOCAL app.allow_immutable_delete = 'on'")
        else:
            cursor.execute("SET LOCAL session_replication_role = 'replica'")

        # Staff retirement has completed and immutable deletion is now authorized.
        # The provider owner removes tenant-private rows while retaining shared
        # sender suppression/aliases; never collect through a shared sender.
        from apps.integrations.notification_privacy import prepare_tenant_purge
        prepare_tenant_purge(makerspace)
        from apps.integrations.messaging.purge import purge_channel
        purge_channel(makerspace, "sms")
        purge_channel(makerspace, "whatsapp")
        from apps.integrations.models_contract import NotificationEnvelope
        from apps.integrations.models_endpoints import ChannelConfiguration
        # Canonical sends/proofs cannot outlive whole-tenant deletion. They are
        # independent of the optional inbox, so its module collector leaves them.
        NotificationEnvelope.objects.filter(makerspace=makerspace).delete()
        ChannelConfiguration.objects.filter(makerspace=makerspace).delete()

        QrPrintBatch.objects.filter(makerspace=makerspace).delete()
        StockTransfer.objects.filter(
            Q(makerspace=makerspace)
            | Q(source_makerspace=makerspace)
            | Q(destination_makerspace=makerspace)
            | Q(source_container__makerspace=makerspace)
            | Q(destination_container__makerspace=makerspace)
            | Q(lines__product__makerspace=makerspace)
            | Q(lines__asset__makerspace=makerspace)
        ).distinct().delete()
        StocktakeSession.objects.filter(makerspace=makerspace).delete()
        InventoryAdjustment.objects.filter(makerspace=makerspace).delete()
        # Organizations are platform-level and may be shared by other tenants. Remove
        # only this tenant's through rows; never traverse from the organization side.
        OrganizationMakerspace.objects.filter(makerspace=makerspace).delete()

        delete_for_makerspace(makerspace, cursor)

        HardwareRequestItemAsset.objects.filter(request_item__request__makerspace=makerspace).delete()
        BoxScan.objects.filter(makerspace=makerspace).delete()
        QrScanEvent.objects.filter(makerspace=makerspace).delete()
        PublicToolLoan.objects.filter(makerspace=makerspace).delete()
        RequesterAccountability.objects.filter(makerspace=makerspace).delete()
        ReturnEvent.objects.filter(makerspace=makerspace).delete()
        HardwareRequest.objects.filter(makerspace=makerspace).delete()
        # Both photo sidecars are PROTECT: delete them explicitly first. FK-free
        # abandoned-upload receipts are deliberately left to keep reconciling.
        EvidenceUploadFinalization.objects.filter(evidence__makerspace=makerspace).delete()
        EvidenceObjectRetentionState.objects.filter(evidence__makerspace=makerspace).delete()
        EvidencePhoto.objects.filter(makerspace=makerspace).delete()
        EvidenceRetentionPolicy.objects.filter(makerspace=makerspace).delete()
        QrCode.objects.filter(makerspace=makerspace).delete()

        # Machines + their maintenance/children/consumables cascade from the Machine
        # delete (triggers suspended above). Do this BEFORE InventoryProduct because
        # MachineConsumable.product is PROTECT; and clear the makerspace-scoped custom
        # MachineType (PROTECT makerspace FK) before makerspace.delete().
        Machine.objects.filter(makerspace=makerspace).delete()
        MakerspaceMachineTypePricing.objects.filter(makerspace=makerspace).delete()
        MakerspaceMachineTypePolicy.objects.filter(makerspace=makerspace).delete()
        MachineType.objects.filter(makerspace=makerspace).delete()

        InventoryAsset.objects.filter(makerspace=makerspace).delete()
        InventoryProduct.objects.filter(makerspace=makerspace).delete()
        Category.objects.filter(makerspace=makerspace).delete()
        Box.objects.filter(makerspace=makerspace).delete()

        EmailTemplate.objects.filter(makerspace=makerspace).delete()
        MachineTypeEmailTemplate.objects.filter(makerspace=makerspace).delete()
        ApiClient.objects.filter(makerspace=makerspace).delete()
        ApiKeyRequest.objects.filter(makerspace=makerspace).delete()

        # Native app registrations are makerspace-scoped, but DeviceGrant.registration and
        # DeviceAttestationChallenge.registration are PROTECT, so letting the makerspace
        # CASCADE into them raises ProtectedError and the whole purge fails -- the same
        # shape as MachineConsumable.product below. Clear the dependent authentication
        # rows first. Grants are deliberately destroyed: they are authority to act inside
        # a space that no longer exists.
        registrations = NativeAppRegistration.objects.filter(makerspace=makerspace)
        DeviceRefreshToken.objects.filter(
            family__grant__registration__in=registrations
        ).delete()
        DeviceRefreshFamily.objects.filter(
            grant__registration__in=registrations
        ).delete()
        DeviceGrant.objects.filter(registration__in=registrations).delete()
        DeviceAttestationChallenge.objects.filter(
            registration__in=registrations
        ).delete()
        registrations.delete()
        # Applications PROTECT their selected plans. Remove module-owned children
        # before RBAC memberships and the final makerspace cascade collect plans.
        from apps.makerspaces.module_purge_collectors_membership import membership_delete

        membership_delete(makerspace, cursor)
        from apps.presence.purge import delete as presence_delete
        presence_delete(makerspace, cursor)
        MakerspaceMembership.objects.filter(makerspace=makerspace).delete()
        # AuditBatchLeaf.audit_log PROTECTs the audit rows deleted just below, and the
        # batch FK PROTECTs the makerspace itself, so both must go first. Attestation is
        # deployment-local state about rows that are being destroyed anyway.
        # Verification runs PROTECT the makerspace and their events CASCADE from the run;
        # delete events first so the order is explicit rather than cascade-implied.
        AuditVerificationRunEvent.objects.filter(run__makerspace=makerspace).delete()
        AuditVerificationRun.objects.filter(makerspace=makerspace).delete()
        AuditBatchLeaf.objects.filter(batch__makerspace=makerspace).delete()
        AuditBatch.objects.filter(makerspace=makerspace).delete()
        AuditSigningKeyRotationEvent.objects.filter(
            rotation__makerspace=makerspace
        ).delete()
        # Break the row-local pending claim before deleting immutable transitions.
        AuditSigningKey.objects.filter(makerspace=makerspace).update(
            pending_rotation=None
        )
        AuditSigningKeyRotation.objects.filter(makerspace=makerspace).delete()
        AuditLog.objects.filter(makerspace=makerspace).delete()
        # Manual settlements cascade with their payments (triggers are suspended for
        # this transaction), so the cash book needs no separate pass. Refunds do NOT:
        # `Refund.payment` is PROTECT, so they go first or any space that ever refunded
        # a charge raises ProtectedError here and can never be purged.
        # Refund cases PROTECT both their payment and their refund, so they go first.
        RefundCase.objects.filter(payment__makerspace=makerspace).delete()
        Refund.objects.filter(payment__makerspace=makerspace).delete()
        Payment.objects.filter(makerspace=makerspace).delete()
        ProcessedStripeEvent.objects.filter(makerspace=makerspace).delete()
        # An elsewhere-hosted registration can reference this space's waiver. Clear all
        # three evidence fields or PROTECT would raise ProtectedError in the final cascade.
        EventRegistration.objects.filter(host_waiver__makerspace=makerspace).update(
            host_waiver=None, host_waiver_accepted_at=None,
            host_waiver_version_accepted=None,
        )
        # Organizer attribution is owned by the hosted event, never by whichever
        # makerspaces happen to be linked to its deployment-global organization.
        EventOrganizer.objects.filter(event__makerspace=makerspace).delete()
        EventAudienceOrganization.objects.filter(event__makerspace=makerspace).delete()
        from .lifecycle_purge_reimbursements import delete_reimbursement_graph
        delete_reimbursement_graph(makerspace, cursor)
        from .purge_events_programme import delete_programme_rows
        delete_programme_rows(makerspace)
        EventAttendanceCertificate.objects.filter(
            event__makerspace=makerspace
        ).delete()
        from apps.events.models import EventCertificateArtwork, EventCertificateTemplateRevision
        EventCertificateTemplateRevision.objects.filter(event__makerspace=makerspace).delete()
        EventCertificateArtwork.objects.filter(event__makerspace=makerspace).delete()
        EventFeedbackResponse.objects.filter(
            survey__event__makerspace=makerspace
        ).delete()
        EventFeedbackSurvey.objects.filter(event__makerspace=makerspace).delete()
        StationCredential.objects.filter(station__makerspace=makerspace).delete()
        EventStaffGrantInvite.objects.filter(makerspace=makerspace).delete()
        EventStaffGrant.objects.filter(makerspace=makerspace).delete()
        from apps.bookings.models_broadcasts import BookingBroadcast
        BookingBroadcast.objects.filter(makerspace=makerspace).delete()
        from apps.events.models_broadcasts import EventBroadcast
        EventBroadcast.objects.filter(makerspace=makerspace).delete()
        EventStationBinding.objects.filter(station__makerspace=makerspace).delete()
        EventCheckInEvent.objects.filter(makerspace=makerspace).delete()
        # Registrations otherwise survive until the final makerspace cascade. Delete
        # hosted rows explicitly so any PROTECT FK they gain cannot fail that cascade;
        # collaborator provenance must not remove another host's registration.
        EventRegistration.objects.filter(event__makerspace=makerspace).delete()
        EventCollaborator.objects.filter(
            source_series_collaboration__makerspace=makerspace
        ).exclude(event__makerspace=makerspace).delete()
        EventSeriesCollaborator.objects.filter(makerspace=makerspace).delete()
        from apps.events.models_website import EventPage
        EventPage.objects.filter(makerspace=makerspace).delete()
        Event.objects.filter(makerspace=makerspace).delete()
        EventSeries.objects.filter(makerspace=makerspace).delete()
        # Credentials and event bindings are already gone. Delete every Station kind so
        # scanner/handover metadata cannot outlive a whole-tenant purge either.
        Station.objects.filter(makerspace=makerspace).delete()
        # Encryption key rows carry a PROTECT FK + a no-delete ORM guard/trigger, so
        # raw-delete them inside this authorized purge context (session_replication_role
        # =replica self-host, or app.allow_immutable_delete GUC managed) before the
        # parent delete; otherwise the PROTECT FK would block teardown once a makerspace
        # has ever had scoped-PII encryption enabled.
        cursor.execute(
            "DELETE FROM encryption_makerspaceencryptionkey WHERE makerspace_id = %s",
            [makerspace.id],
        )
        cursor.execute(
            "DELETE FROM encryption_piimakerspacewritefence WHERE makerspace_id = %s",
            [makerspace.id],
        )
        RestoreRollbackObject.objects.filter(makerspace=makerspace).delete()
        # TenantImportJob deliberately uses SET_NULL so an ordinary tenant deletion is
        # possible. Purge must delete the jobs first or that safety valve would strand
        # target-side identity decisions after their tenant disappeared.
        TenantImportJob.objects.filter(target_makerspace=makerspace).delete()
        # Generic provenance has no FK to the source/anchor rows it describes, so
        # delete it explicitly rather than relying on the makerspace CASCADE.
        ExternalTenantReference.objects.filter(makerspace=makerspace).delete()
        from apps.bookings.models_arrival import BookingCheckInEvent
        BookingCheckInEvent.objects.filter(booking__space__makerspace=makerspace).delete()
        from apps.bookings.purge_p2 import delete_departure_history
        delete_departure_history(makerspace)
        makerspace.delete()
