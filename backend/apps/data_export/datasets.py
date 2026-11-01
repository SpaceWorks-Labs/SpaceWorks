"""Per-fidelity dataset/output registry."""

from django.apps import apps

from .fields import FIELDS
from .models import EXPORTED_MODELS
from .types import Column, Dataset, Fidelity, Omitted, TenantPredicate, Transformed

P = TenantPredicate

# A dataset has one root model.  Relationship values are IDs/snapshots; a dataset may
# never expand a routing relation into the related tenant's row.
DATASET_SPECS = {
    "presence.PresenceSettings": ("presence/settings.csv", P(("makerspace",))),
    "presence.PresencePreference": ("presence/preferences.csv", P(("makerspace",))),
    "makerspaces.PublicHandle": ("members/public_handles.csv", P(("profile__membership__makerspace", "makerspace"))),
    "makerspaces.ProfileTimelineEntry": ("members/timeline.csv", P(("profile__membership__makerspace",))),
    "bookings.BookingResourcePage": ("bookings/pages.csv", P(("space__makerspace",))),
    "bookings.BookingResourcePageAsset": ("bookings/page_assets.csv", P(("page__space__makerspace",))),
    "bookings.BookingResourcePageSection": ("bookings/page_sections.csv", P(("page__space__makerspace",))),
    "bookings.BookingBroadcast": ("bookings/broadcasts.csv", P(("makerspace",), ("space__makerspace",))),
    "bookings.BookingBroadcastDelivery": ("bookings/broadcast_deliveries.csv", P(("campaign__makerspace",))),
    "events.EventPage": ("events/pages.csv", P(("makerspace",))),
    "events.EventPageAsset": ("events/page_assets.csv", P(("page__makerspace",))),
    "events.EventPageSection": ("events/page_sections.csv", P(("page__makerspace",))),
    "events.EventSession": ("events/sessions.csv", P(("page__makerspace",))),
    "events.EventSessionSpeaker": ("events/session_speakers.csv", P(("session__page__makerspace",))),
    "events.EventBroadcast": ("events/broadcasts.csv", P(("makerspace",), ("event__makerspace",))),
    "events.EventBroadcastDelivery": ("events/broadcast_deliveries.csv", P(("campaign__makerspace",))),
    "makerspaces.MembershipAdditionalRole": ("members/additional_roles.csv", P(("membership__makerspace",), ("role__makerspace",))),
    "machines.MembershipMachineTypeScope": ("members/member_machine_type_scopes.csv", P(("membership__makerspace",), ("machine_type__makerspace",))),
    "notifications.MemberNotificationPreference": ("notifications/member_preferences.csv", P(("makerspace",))),
    "notifications.NotificationPreference": ("notifications/personal_preferences.csv", P(("makerspace",))),
    "operations.SavedView": ("preferences/saved_views.csv", P(("makerspace",))),
    "makerspaces.MakerspaceLoanPolicy": ("makerspace/loan_policy.csv", P(("makerspace",))),
    "apiclients.ApiClient": ("makerspace/api_clients.csv", P(("makerspace",))),
    "apiclients.ApiKeyRequest": ("makerspace/api_key_requests.csv", P(("makerspace",))),
    "audit.AuditLog": ("audit/audit_log.csv", P(("makerspace",))),
    "bookings.BookableSpace": ("bookings/spaces.csv", P(("makerspace",))),
    "bookings.BookingCheckInEvent": ("bookings/arrival_history.csv", P(("booking__space__makerspace",))),
    "bookings.Booking": ("bookings/bookings.csv", P(("space__makerspace",))),
    "boxes.Box": ("inventory/containers_and_boxes.csv", P(("makerspace",))),
    "boxes.BoxScan": ("lending/box_scans.csv", P(("makerspace",), ("box__makerspace",))),
    "boxes.QrCode": ("inventory/qr_mappings.csv", P(("makerspace",))),
    "boxes.QrScanEvent": ("lending/qr_scan_events.csv", P(("makerspace",), ("qr_code__makerspace",))),
    "devices.Device": ("devices/devices.csv", P(("makerspace",))),
    "devices.DeviceEvent": ("devices/events.csv", P(("makerspace",), ("device__makerspace",))),
    "events.Event": ("events/events.csv", P(("makerspace",))),
    "events.EventSeries": ("events/series.csv", P(("makerspace",))),
    "events.EventSeriesCollaborator": ("events/series_collaborators.csv", P(("series__makerspace", "makerspace"))),
    "events.EventCollaborator": ("events/collaborators.csv", P(("event__makerspace", "makerspace"))),
    "events.EventRegistration": ("events/registrations.csv", P(("event__makerspace",))),
    "events.EventCheckInEvent": ("events/check_in_history.csv", P(("makerspace",))),
    "events.EventStationBinding": ("events/station_bindings.csv", P(("event__makerspace",))),
    "events.EventFeedbackSurvey": ("events/feedback_surveys.csv", P(("event__makerspace",))),
    "events.EventFeedbackResponse": ("events/feedback_responses.csv", P(("survey__event__makerspace",))),
    "events.EventAttendanceCertificate": ("events/attendance_certificates.csv", P(("event__makerspace",))),
    "events.EventCertificateArtwork": ("events/certificate_artwork.csv", P(("event__makerspace",))),
    "events.EventCertificateTemplateRevision": ("events/certificate_template_revisions.csv", P(("event__makerspace",))),
    "evidence.EvidencePhoto": ("evidence/photos.csv", P(("makerspace",))),
    "evidence.EvidenceObjectRetentionState": (
        "evidence/object_retention.csv",
        P(("evidence__makerspace",)),
    ),
    "evidence.EvidenceRetentionPolicy": (
        "evidence/retention_policy.csv",
        P(("makerspace",)),
    ),
    "hardware_requests.HardwareRequest": ("lending/requests.csv", P(("makerspace",))),
    "hardware_requests.HardwareRequestItem": ("lending/request_items.csv", P(("request__makerspace",))),
    "hardware_requests.HardwareRequestItemAsset": ("lending/request_item_assets.csv", P(("request_item__request__makerspace",))),
    "hardware_requests.PublicProblemReport": ("lending/problem_reports.csv", P(("makerspace",))),
    "hardware_requests.PublicToolLoan": ("lending/direct_and_self_checkout_loans.csv", P(("makerspace",))),
    "hardware_requests.RequesterAccountability": ("lending/accountability.csv", P(("makerspace",))),
    "hardware_requests.ReturnEvent": ("lending/return_events.csv", P(("makerspace",))),
    "integrations.ChatTemplate": ("notifications/chat_templates.csv", P(("makerspace",))),
    "integrations.DestinationCategoryScope": ("notifications/destination_category_scopes.csv", P(("destination__makerspace",), ("category__makerspace",))),
    "integrations.DestinationMachineScope": ("notifications/destination_machine_scopes.csv", P(("destination__makerspace",), ("machine__makerspace",))),
    "integrations.DestinationMachineTypeScope": ("notifications/destination_machine_type_scopes.csv", P(("destination__makerspace",), ("machine_type__makerspace",))),
    "integrations.EmailNotificationMute": ("notifications/email_mutes.csv", P(("makerspace",))),
    "integrations.EmailTemplate": ("notifications/email_templates.csv", P(("makerspace",))),
    "integrations.MachineTypeEmailTemplate": ("notifications/machine_type_email_templates.csv", P(("makerspace",), ("machine_type__makerspace",))),
    "integrations.NotificationDestination": ("notifications/destinations.csv", P(("makerspace",))),
    "integrations.NotificationPreference": ("notifications/preferences.csv", P(("makerspace",))),
    "integrations.NotificationRecipient": ("notifications/recipients.csv", P(("makerspace",))),
    "integrations.RecipientCategoryScope": ("notifications/recipient_category_scopes.csv", P(("recipient__makerspace",), ("category__makerspace",))),
    "integrations.RecipientMachineScope": ("notifications/recipient_machine_scopes.csv", P(("recipient__makerspace",), ("machine__makerspace",))),
    "integrations.RecipientMachineTypeScope": ("notifications/recipient_machine_type_scopes.csv", P(("recipient__makerspace",), ("machine_type__makerspace",))),
    "inventory.Category": ("inventory/categories.csv", P(("makerspace",))),
    "inventory.InventoryAsset": ("inventory/assets.csv", P(("makerspace",), ("product__makerspace", "box__makerspace"))),
    "inventory.InventoryProduct": ("inventory/products.csv", P(("makerspace",), ("box__makerspace", "category__makerspace"))),
    "machines.Machine": ("machines/machines.csv", P(("makerspace",), ("machine_type__makerspace",))),
    "machines.MachineConsumable": ("machines/consumables.csv", P(("machine__makerspace",), ("product__makerspace",))),
    "machines.MachineConsumableAdjustment": ("machine_service/consumable_adjustments.csv", P(("makerspace",), ("consumable_pool__makerspace",))),
    "machines.MachineConsumablePool": ("machine_service/consumable_pools.csv", P(("makerspace",), ("machine__makerspace",))),
    "machines.MachineDocument": ("machines/documents.csv", P(("machine__makerspace",))),
    "machines.MachineErrorLog": ("machines/error_logs.csv", P(("machine__makerspace",))),
    "machines.MachineOperator": ("machines/operators.csv", P(("machine__makerspace",))),
    "machines.MachineServiceRequest": ("machine_service/requests.csv", P(("makerspace",))),
    "machines.CertificationGrant": ("machines/certification_grants.csv", P(("certification_type__makerspace",))),
    "machines.MakerspaceMachineTypePolicy": ("machines/type_policies.csv", P(("makerspace",))),
    "machines.CertificationType": ("machines/certification_types.csv", P(("makerspace",))),
    "machines.MachineType": ("machines/types.csv", P(("makerspace",), include_global_if_unowned=True)),
    "machines.MachineUsageEntry": ("machines/usage_entries.csv", P(("machine__makerspace",))),
    "machines.MakerspaceMachineTypePricing": ("machines/type_pricing.csv", P(("makerspace",), ("machine_type__makerspace",))),
    "machines.ServiceBucket": ("machine_service/buckets.csv", P(("machine__makerspace",))),
    "machines.ServiceQueue": ("machine_service/queues.csv", P(("makerspace",), ("machine_type__makerspace",))),
    "machines.ServiceRequestConsumption": ("machine_service/request_consumptions.csv", P(("service_request__makerspace",), ("machine_consumable__machine__makerspace",))),
    "machines.ServiceRequestFile": ("machine_service/files.csv", P(("makerspace",))),
    "maintenance.MaintenanceLog": ("maintenance/logs.csv", P(("machine__makerspace",))),
    "maintenance.MaintenanceLogDocument": ("maintenance/documents.csv", P(("log__machine__makerspace",))),
    "maintenance.MaintenanceSchedule": ("maintenance/schedules.csv", P(("machine__makerspace",))),
    "makerspaces.Makerspace": ("makerspace/config.csv", P(("pk",))),
    "makerspaces.MakerspaceMembership": ("members/roster.csv", P(("makerspace",))),
    "makerspaces.MakerspaceRole": ("members/roles.csv", P(("makerspace",))),
    "makerspaces.ModuleSettingsGrant": ("makerspace/settings_grants.csv", P(("makerspace",))),
    "makerspaces.ModuleSettingLock": ("makerspace/setting_locks.csv", P(("makerspace",))),
    "makerspaces.MakerspaceWaiver": ("members/waivers.csv", P(("makerspace",))),
    "makerspaces.MemberCard": ("members/member_cards.csv", P(("makerspace",))),
    "makerspaces.MemberProfile": ("members/profiles.csv", P(("membership__makerspace",))),
    "makerspaces.MemberProject": ("members/projects.csv", P(("profile__membership__makerspace",))),
    "makerspaces.MembershipRequest": ("members/membership_requests.csv", P(("makerspace",), ("selected_plan__makerspace", "admission_payment__makerspace"))),
    "makerspaces.MakerspaceMembershipSettings": ("members/admission_settings.csv", P(("makerspace",), ("default_plan__makerspace",))),
    "makerspaces.MembershipVouch": ("members/membership_vouches.csv", P(("makerspace",), ("request__makerspace",))),
    "makerspaces.MembershipPlan": ("members/membership_plans.csv", P(("makerspace",))),
    "makerspaces.MembershipTerm": ("members/membership_terms.csv", P(("membership__makerspace",))),
    "makerspaces.InvitationRequest": ("members/invitation_requests.csv", P(("makerspace",))),
    "makerspaces.Station": ("makerspace/stations.csv", P(("makerspace",))),
    "notifications.Notification": ("notifications/inbox.csv", P(("makerspace",))),
    "operations.InventoryAdjustment": ("operations/inventory_adjustments.csv", P(("makerspace",))),
    "operations.QrPrintBatch": ("operations/qr_print_batches.csv", P(("makerspace",))),
    "operations.QrPrintBatchItem": ("operations/qr_print_batch_items.csv", P(("batch__makerspace",))),
    "operations.ReportMetricRollup": ("reports/metric_rollups.csv", P(("makerspace",))),
    "operations.ReportSchedule": ("reports/schedules.csv", P(("makerspace",))),
    "operations.StocktakeLedgerEntry": ("stocktake/ledger.csv", P(("makerspace",), ("stocktake__makerspace",))),
    "operations.StocktakeLine": ("stocktake/lines.csv", P(("stocktake__makerspace",), ("product__makerspace", "asset__makerspace", "container__makerspace"))),
    "operations.StocktakeSession": ("stocktake/sessions.csv", P(("makerspace",), ("container__makerspace",))),
    "operations.StockTransfer": ("transfers/transfers.csv", P(("makerspace", "source_makerspace", "destination_makerspace"))),
    "operations.StockTransferLine": ("transfers/lines.csv", P(("transfer__makerspace", "transfer__source_makerspace", "transfer__destination_makerspace"))),
    "payments.MakerspacePaymentSettings": ("makerspace/payment_settings.csv", P(("makerspace",))),
    "payments.Payment": ("payments/payments.csv", P(("makerspace",))),
    "payments.PaymentDocument": ("payments/documents.csv", P(("makerspace",))),
    "payments.MakerspaceBillingSettings": ("makerspace/billing_settings.csv", P(("makerspace",))),
    "payments.ManualSettlement": ("payments/manual_settlements.csv", P(("payment__makerspace",))),
    "payments.Refund": ("payments/refunds.csv", P(("payment__makerspace",))),
    "payments.RefundCase": ("payments/refund_cases.csv", P(("payment__makerspace",))),
    "payments.RefundPolicy": ("makerspace/refund_policies.csv", P(("makerspace",))),
    "presence.PresenceSession": ("presence/sessions.csv", P(("makerspace",))),
    "procurement.ToBuyItem": ("procurement/to_buy_items.csv", P(("makerspace",))),
    "procurement.ToBuyReceipt": ("procurement/receipts.csv", P(("to_buy_item__makerspace",))),
    "tenant_migration.ExternalTenantReference": ("migration/external_references.csv", P(("makerspace",))),
    "warranty.Warranty": ("warranty/warranties.csv", P(("makerspace",), ("asset__makerspace", "machine__makerspace"))),
    "warranty.WarrantyDocument": ("warranty/documents.csv", P(("warranty__makerspace",))),
}


from .datasets_7b import printer_dataset_specs

DATASET_SPECS.update(printer_dataset_specs(P))

from .datasets_7c import LABEL_DATASET_SPECS

DATASET_SPECS.update(LABEL_DATASET_SPECS)
from .datasets_wp4 import DATASET_SPECS as WP4_DATASETS
DATASET_SPECS.update(WP4_DATASETS)


def _columns(fidelity, label):
    model = apps.get_model(label)
    columns = []
    omissions = {}
    for field in model._meta.get_fields():
        disposition = FIELDS.get((fidelity, label, field.name))
        if disposition is None:
            continue
        if isinstance(disposition, Omitted):
            omissions[field.name] = disposition.reason
            continue
        columns.append(Column(field.attname, (field.name,), disposition))
    if label == "audit.AuditLog":
        columns.append(
            Column(
                "actor_username",
                ("actor__username",),
                Transformed("Intentional identifying disclosure for a referenced audit actor."),
            )
        )
    return tuple(columns), omissions


from .datasets_w7_events import EVENT_DATASET_SPECS
DATASET_SPECS.update(EVENT_DATASET_SPECS)
from apps.tenant_migration.catalog_p2_bookings import DATASETS as P2_BOOKING_DATASETS
DATASET_SPECS.update({label: (path, P(paths)) for label, (path, paths) in P2_BOOKING_DATASETS.items()})

DATASET_SPECS.update({
    "inventory.InventoryStockSnapshot": ("inventory/stock_snapshots.csv", P(("makerspace",), ("product__makerspace",))),
    "machines.MachineStatusEvent": ("machines/status_events.csv", P(("makerspace",), ("machine__makerspace",))),
    "machines.ConsumableCostRecord": ("machines/consumable_costs.csv", P(("makerspace",))),
})
DATASET_SPECS.update({
    "integrations.WhatsAppTemplateBinding": ("messaging/whatsapp_templates.csv", P(("makerspace",))),
    "integrations.MessagingConsent": ("messaging/consents.csv", P(("makerspace",))),
})
from apps.tenant_migration.catalog_events_programme_references import DATASETS as PROGRAMME_DATASETS
DATASET_SPECS.update({label: (path, P((owner,))) for label, (path, owner) in PROGRAMME_DATASETS.items()})
from apps.tenant_migration.catalog_reimbursements import DATASETS as REIMBURSEMENT_DATASETS
DATASET_SPECS.update({label: (path, P((owner,))) for label, (path, owner) in REIMBURSEMENT_DATASETS.items()})
DATASETS = {}
from .datasets_wp3 import wp3_dataset_specs
DATASET_SPECS.update(wp3_dataset_specs(P))
from apps.tenant_migration.catalog_public_pages import DATASETS as PAGE_DATASETS
DATASET_SPECS.update({label: (path, P((owner_path,))) for label, (path, owner_path) in PAGE_DATASETS.items()})

_MODEL_KEYSETS = {
    "evidence.EvidenceObjectRetentionState": ("evidence_id",),
    "evidence.EvidenceRetentionPolicy": ("makerspace_id",),
}
from .classification_r2_l1 import DATASET_SPECS as R2_L1_DATASETS  # noqa: E402
DATASET_SPECS.update(R2_L1_DATASETS)
from .classification_r2_l4 import DATASET_SPECS as R2_L4_DATASETS  # noqa: E402
DATASET_SPECS.update(R2_L4_DATASETS)
from .classification_r2_l5 import DATASET_SPECS as R2_L5_DATASETS  # noqa: E402
DATASET_SPECS.update(R2_L5_DATASETS)
from .classification_login_security import DATASET_SPECS as S0_DATASETS  # noqa: E402
DATASET_SPECS.update(S0_DATASETS)
from .classification_r2_l15 import DATASET_SPECS as R2_L15_DATASETS  # noqa: E402
DATASET_SPECS.update(R2_L15_DATASETS)
for _fidelity in Fidelity:
    for _label, (_path, _predicate) in DATASET_SPECS.items():
        _columns_for_dataset, _omissions = _columns(_fidelity, _label)
        DATASETS[(_fidelity, _path)] = Dataset(
            fidelity=_fidelity,
            path=_path,
            model=_label,
            predicate=_predicate,
            keyset=_MODEL_KEYSETS.get(_label, ("id",)),
            columns=_columns_for_dataset,
            explicit_omissions=_omissions,
        )

# Global users are selected by USER_EDGES rather than a tenant FK predicate.
for _fidelity in Fidelity:
    _columns_for_dataset, _omissions = _columns(_fidelity, "accounts.User")
    DATASETS[(_fidelity, "global/users.csv")] = Dataset(
        fidelity=_fidelity,
        path="global/users.csv",
        model="accounts.User",
        predicate=P(("closure",)),
        keyset=("id",),
        columns=_columns_for_dataset,
        explicit_omissions=_omissions,
    )

assert EXPORTED_MODELS == frozenset(DATASET_SPECS)
