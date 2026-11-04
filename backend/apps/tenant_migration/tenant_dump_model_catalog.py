"""Exact model/table universes for ``spaceworks-tenant-dump-v1``."""

from apps.data_export.models import OMITTED_MODELS

from .tenant_dump_types import ModelDisposition, ModelRule, TableRule


FIRST_PARTY_APP_LABELS = frozenset(
    """accounts admin_api apiclients audit backup bookings boxes card_designs data_export devices
    encryption event_reimbursements events evidence hardware_requests hosting_requests id_programmes integrations
    inventory machines
    maintenance makerspaces notifications operations organizations payments payments_rail
    presence
    printing procurement roadmap separability tenant_migration warranty""".split()
)
THIRD_PARTY_MODEL_APP_LABELS = frozenset(
    {"admin", "auth", "axes", "contenttypes", "sessions", "token_blacklist"}
)
THIRD_PARTY_INSTALLED_APP_LABELS = frozenset(
    """unfold unfold_filters admin auth axes contenttypes postgres sessions messages
    staticfiles rest_framework drf_spectacular rest_framework_simplejwt token_blacklist
    corsheaders storages""".split()
)

# These labels are literal. A new exported model must be placed here deliberately;
# deriving this set from data_export.EXPORTED_MODELS would let it travel before a
# Lane-D-specific review.
PROJECTED_MODEL_LABELS = frozenset(
    """operations.SavedView accounts.User apiclients.ApiKeyRequest audit.AuditLog
    makerspaces.MembershipAdditionalRole machines.MembershipMachineTypeScope
    notifications.MemberNotificationPreference notifications.NotificationPreference
    bookings.BookableSpace bookings.Booking boxes.Box
    boxes.BoxScan boxes.QrCode boxes.QrScanEvent devices.Device devices.DeviceEvent
    events.EventSeries events.Event events.EventRegistration
    events.EventCheckInEvent events.EventStationBinding events.EventFeedbackSurvey events.EventFeedbackResponse
    events.EventAttendanceCertificate
    events.EventCertificateArtwork events.EventCertificateTemplateRevision
    evidence.EvidencePhoto evidence.EvidenceObjectRetentionState
    evidence.EvidenceRetentionPolicy hardware_requests.HardwareRequest
    hardware_requests.HardwareRequestItem hardware_requests.HardwareRequestItemAsset
    hardware_requests.PublicProblemReport hardware_requests.PublicToolLoan
    hardware_requests.RequesterAccountability hardware_requests.ReturnEvent
    integrations.ChatTemplate integrations.DestinationCategoryScope
    integrations.DestinationMachineScope integrations.DestinationMachineTypeScope
    integrations.EmailTemplate integrations.MachineTypeEmailTemplate
    integrations.NotificationDestination inventory.Category inventory.InventoryAsset
    inventory.InventoryProduct machines.CertificationGrant machines.CertificationType
    machines.Machine machines.MachineConsumable
    machines.MachineConsumableAdjustment machines.MachineConsumablePool
    machines.MachineDocument machines.MachineErrorLog machines.MachineServiceRequest
    machines.MachineType machines.MachineUsageEntry
    machines.MakerspaceMachineTypePricing machines.MakerspaceMachineTypePolicy machines.ServiceBucket machines.ServiceQueue
    machines.ServiceRequestConsumption machines.ServiceRequestFile
    maintenance.MaintenanceLog maintenance.MaintenanceLogDocument
    maintenance.MaintenanceSchedule makerspaces.Makerspace
    makerspaces.MakerspaceLoanPolicy makerspaces.MakerspaceMembership makerspaces.MakerspaceWaiver
    makerspaces.MemberCard makerspaces.MemberProfile makerspaces.MemberProject
    makerspaces.MembershipRequest makerspaces.MembershipPlan makerspaces.MembershipTerm
    makerspaces.MakerspaceMembershipSettings makerspaces.MembershipVouch
    makerspaces.InvitationRequest makerspaces.Station
    notifications.Notification operations.InventoryAdjustment operations.QrPrintBatch
    operations.QrPrintBatchItem operations.ReportMetricRollup operations.StockTransfer
    operations.StockTransferLine
    operations.StocktakeLedgerEntry operations.StocktakeLine operations.StocktakeSession
    payments.MakerspacePaymentSettings payments.MakerspaceBillingSettings payments.ManualSettlement payments.Payment
    payments.Refund payments.RefundCase payments.RefundPolicy payments.PaymentDocument presence.PresenceSession
    makerspaces.ModuleSettingsGrant makerspaces.ModuleSettingLock
    procurement.ToBuyItem procurement.ToBuyReceipt
    tenant_migration.ExternalTenantReference warranty.Warranty
    warranty.WarrantyDocument""".split()
)

from .catalog_7b import PRINTER_PROJECTED_LABELS

PROJECTED_MODEL_LABELS |= PRINTER_PROJECTED_LABELS

from .catalog_7c import LABEL_PROJECTED_MODELS

PROJECTED_MODEL_LABELS |= LABEL_PROJECTED_MODELS
from .catalog_wp4 import PROJECTED_LABELS as WP4_PROJECTED_LABELS
PROJECTED_MODEL_LABELS |= WP4_PROJECTED_LABELS

from .catalog_w7_events import EVENT_PROJECTED_MODELS
PROJECTED_MODEL_LABELS |= EVENT_PROJECTED_MODELS
from .catalog_broadcasts import FIELD_NAMES as BROADCAST_FIELDS
PROJECTED_MODEL_LABELS |= BROADCAST_FIELDS.keys()
from .catalog_website import FIELD_NAMES as WEBSITE_FIELDS
PROJECTED_MODEL_LABELS |= WEBSITE_FIELDS.keys()

from .catalog_wp3 import WP3_PROJECTED_LABELS
PROJECTED_MODEL_LABELS |= WP3_PROJECTED_LABELS

from .catalog_booking_arrival import FIELD_NAMES as BOOKING_ARRIVAL_FIELDS
PROJECTED_MODEL_LABELS |= BOOKING_ARRIVAL_FIELDS.keys()
from .catalog_p2_bookings import FIELD_NAMES as P2_BOOKING_FIELDS
PROJECTED_MODEL_LABELS |= P2_BOOKING_FIELDS.keys()
from .catalog_r2_l1 import FIELD_NAMES as R2_L1_FIELDS  # noqa: E402
PROJECTED_MODEL_LABELS |= R2_L1_FIELDS.keys()
from .catalog_r2_l4 import PROJECTED_LABELS as R2_L4_PROJECTED  # noqa: E402
PROJECTED_MODEL_LABELS |= R2_L4_PROJECTED
from .catalog_r2_l5 import PROJECTED_LABELS as R2_L5_PROJECTED  # noqa: E402
PROJECTED_MODEL_LABELS |= R2_L5_PROJECTED
from .catalog_login_security import PROJECTED_LABELS as S0_PROJECTED_LABELS  # noqa: E402
PROJECTED_MODEL_LABELS |= S0_PROJECTED_LABELS
from .catalog_r2_l15 import PROJECTED_LABELS as R2_L15_PROJECTED  # noqa: E402
PROJECTED_MODEL_LABELS |= R2_L15_PROJECTED
from .catalog_l12 import PROJECTED_LABELS as L12_PROJECTED  # noqa: E402
PROJECTED_MODEL_LABELS |= L12_PROJECTED
from .catalog_l3 import PROJECTED_LABELS as L3_PROJECTED  # noqa: E402
PROJECTED_MODEL_LABELS |= L3_PROJECTED
from .catalog_r2_l6 import PROJECTED_LABELS as R2_L6_PROJECTED  # noqa: E402
PROJECTED_MODEL_LABELS |= R2_L6_PROJECTED
from .catalog_r2_l18 import PROJECTED_LABELS as R2_L18_PROJECTED  # noqa: E402
PROJECTED_MODEL_LABELS |= R2_L18_PROJECTED

from .catalog_profiles import EXPORTED_FIELDS as PROFILE_FIELDS
PROJECTED_MODEL_LABELS |= PROFILE_FIELDS.keys()
from .catalog_public_pages import EXPORTED_FIELDS as PAGE_EXPORTED_FIELDS
PROJECTED_MODEL_LABELS |= PAGE_EXPORTED_FIELDS.keys()

PROJECTED_MODEL_LABELS |= frozenset({"inventory.InventoryStockSnapshot", "machines.MachineStatusEvent", "machines.ConsumableCostRecord"})

PRESERVE_LIVE_MODEL_LABELS = frozenset({"machines.MachineOperator"})

from .catalog_messaging import PROJECTED_LABELS as MESSAGING_PROJECTED_LABELS
PROJECTED_MODEL_LABELS |= MESSAGING_PROJECTED_LABELS

EXPLICIT_DROP_MODEL_REASONS = {
    "apiclients.ApiClient": "Source clients and their bearer secrets never become target authority.",
    "events.EventCollaborator": "Cross-tenant collaboration grants have no target counterpart.",
    "events.EventSeriesCollaborator": "Cross-tenant series collaboration grants have no target counterpart.",
    "integrations.EmailNotificationMute": "Source delivery suppression does not control target mail.",
    "integrations.NotificationPreference": "Target notification defaults are authoritative.",
    "integrations.NotificationRecipient": "Every explicit recipient is a live disclosure rule.",
    "operations.ReportSchedule": "A scheduled report delivery is a live disclosure rule; the target re-creates it.",
    "integrations.RecipientCategoryScope": "The owning disclosure recipient is dropped.",
    "integrations.RecipientMachineScope": "The owning disclosure recipient is dropped.",
    "integrations.RecipientMachineTypeScope": "The owning disclosure recipient is dropped.",
    "makerspaces.MakerspaceRole": "Source roles are replaced by target-seeded protected defaults.",
    "organizations.Organization": "Organizations are deployment-global and do not travel.",
}


from .catalog_p2_presence import model_catalog, DROP_MODELS as PRESENCE_DROPS
PROJECTED_MODEL_LABELS = model_catalog(PROJECTED_MODEL_LABELS)
EXPLICIT_DROP_MODEL_REASONS.update(PRESENCE_DROPS)


def _model_rules():
    rules = {}

    def add(label, rule):
        if label in rules:
            raise RuntimeError(f"duplicate Lane D first-party model rule: {label}")
        rules[label] = rule

    for label in PROJECTED_MODEL_LABELS:
        add(label, ModelRule(
            ModelDisposition.PROJECT,
            "Tenant row travels only after its explicit Lane D field/row projection.",
        ))
    for label, reason in OMITTED_MODELS.items():
        # Includes operations.ReminderSchedule: source-local coordination never
        # travels. Target sources reconstruct it from their imported domain rows.
        add(label, ModelRule(ModelDisposition.DROP, reason))
    for label, reason in EXPLICIT_DROP_MODEL_REASONS.items():
        add(label, ModelRule(ModelDisposition.DROP, reason))
    add("machines.MachineOperator", ModelRule(
        ModelDisposition.PRESERVE_LIVE,
        "Owner decision 22: the exact assignment and provenance travel as live authority.",
    ))
    return rules


from .catalog_events_programme import EXPORTED_FIELDS as PROGRAMME_PROJECTED_FIELDS
PROJECTED_MODEL_LABELS |= PROGRAMME_PROJECTED_FIELDS.keys()
from .catalog_reimbursements import EXPORTED_FIELDS as REIMBURSEMENT_PROJECTED_FIELDS
PROJECTED_MODEL_LABELS |= REIMBURSEMENT_PROJECTED_FIELDS.keys()
FIRST_PARTY_MODEL_RULES = _model_rules()

AUTO_CREATED_TABLE_RULES = {
    "auth.Group_permissions": TableRule(
        ModelDisposition.BOOTSTRAP,
        "Target-seeded Django permission membership only; source rows do not travel.",
    ),
    "accounts.User_groups": TableRule(
        ModelDisposition.EMPTY,
        "Imported users receive no source-global group grants.",
    ),
    "accounts.User_user_permissions": TableRule(
        ModelDisposition.EMPTY,
        "Imported users receive no source-global direct permissions.",
    ),
}

THIRD_PARTY_MODEL_RULES = {
    "admin.LogEntry": TableRule(ModelDisposition.EMPTY, "Deployment-local admin history."),
    "auth.Permission": TableRule(ModelDisposition.BOOTSTRAP, "Seeded by target migrations."),
    "auth.Group": TableRule(ModelDisposition.BOOTSTRAP, "Target-owned Django groups."),
    "axes.AccessFailureLog": TableRule(ModelDisposition.EMPTY, "Source authentication telemetry."),
    "axes.AccessAttempt": TableRule(ModelDisposition.EMPTY, "Source authentication telemetry."),
    "axes.AccessAttemptExpiration": TableRule(ModelDisposition.EMPTY, "Source authentication telemetry."),
    "axes.AccessLog": TableRule(ModelDisposition.EMPTY, "Source authentication telemetry."),
    "contenttypes.ContentType": TableRule(ModelDisposition.BOOTSTRAP, "Seeded by target migrations."),
    "sessions.Session": TableRule(ModelDisposition.EMPTY, "Source bearer sessions never travel."),
    "token_blacklist.OutstandingToken": TableRule(ModelDisposition.EMPTY, "Source bearer tokens never travel."),
    "token_blacklist.BlacklistedToken": TableRule(ModelDisposition.EMPTY, "Source bearer-token state never travels."),
}

UNMANAGED_MODEL_RULES = {}
UNOWNED_TABLE_RULES = {
    "django_migrations": TableRule(
        ModelDisposition.BOOTSTRAP,
        "Scratch and target migrations seed their own schema ledger.",
    ),
    "spaceworks_cache": TableRule(
        ModelDisposition.EMPTY,
        "Discard source cache/throttle rows; runtime repopulates the empty target table.",
    )
}
