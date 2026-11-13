from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import exception_handler
from drf_spectacular.utils import extend_schema_serializer

from apps.accounts.tenant_refusal import outsider_refusal
from apps.hardware_requests.exception_codes import add_error_code

from apps.bookings.exceptions import BookingConflict, BookingInvalidTransition
from apps.accounts.services_claim import ClaimCodeError, ClaimCodeIneligible
from apps.evidence.storage import StorageUnavailable
from apps.events.exceptions import (
    CapacityConflict,
    DuplicateRegistration,
    EventInvalidTransition,
    UseSeriesCollaborators,
    FeedbackConflict,
    FeedbackIneligible,
    RegistrationClosed,
    RegistrationRejected,
)
from apps.hardware_requests.workflow import (
    BoxUnavailable,
    BoxValidationError,
    DepositRequired,
    EvidenceNotUploaded,
    InvalidTransition,
    RequesterBlocked,
    RequestValidationError,
    ReturnValidationError,
)
from apps.inventory.availability import InsufficientStock
from apps.machines.service_errors import (
    ServiceConsumptionInvalid,
    ServiceInsufficientStock,
    ServiceInvalidTransition,
    ServiceMachineUnavailable,
)
from apps.maintenance.exceptions import (
    InactiveMaintenanceSchedule,
    MaintenanceStatusConflict,
    RetiredMachineMaintenance,
)
from apps.machines.member_scope_errors import MemberMachineScopeConflict
from apps.encryption.crypto import PiiUnavailable
from apps.encryption.write_fence import PiiWriteFenced
from apps.presence.guard import (
    MemberPresenceRequired,
    PresenceRequired,
    WaiverAcceptanceRequired,
)


@extend_schema_serializer(component_name="HardwareRequestError")
class ErrorSerializer(serializers.Serializer):
    detail = serializers.CharField()
    code = serializers.CharField()


_EXCEPTION_MAP = {
    MemberMachineScopeConflict: (
        status.HTTP_409_CONFLICT, "member_machine_scope_conflict",
        "Machine scope requires a non-exempt Machine Manager membership.",
    ),
    ClaimCodeError: (
        status.HTTP_400_BAD_REQUEST,
        "invalid_claim_code",
        "Invalid or expired member claim code.",
    ),
    ClaimCodeIneligible: (
        status.HTTP_409_CONFLICT,
        "claim_code_ineligible",
        "This membership is not eligible for a member claim code.",
    ),
    MemberPresenceRequired: (
        status.HTTP_403_FORBIDDEN,
        "membership_required",
        "An active membership is required.",
    ),
    WaiverAcceptanceRequired: (
        status.HTTP_403_FORBIDDEN,
        "waiver_acceptance_required",
        "Accept the current makerspace waiver first.",
    ),
    PresenceRequired: (
        status.HTTP_403_FORBIDDEN,
        "presence_required",
        "An active presence session is required.",
    ),
    PiiWriteFenced: (
        status.HTTP_503_SERVICE_UNAVAILABLE,
        "pii_write_fenced",
        "Protected writes are temporarily unavailable.",
    ),
    PiiUnavailable: (
        status.HTTP_503_SERVICE_UNAVAILABLE,
        "pii_unavailable",
        "Protected data is temporarily unavailable.",
    ),
    RetiredMachineMaintenance: (
        status.HTTP_409_CONFLICT,
        "machine_retired",
        "Machine is retired.",
    ),
    InactiveMaintenanceSchedule: (
        status.HTTP_409_CONFLICT,
        "maintenance_schedule_inactive",
        "Maintenance schedule is inactive.",
    ),
    MaintenanceStatusConflict: (
        status.HTTP_409_CONFLICT,
        "maintenance_status_conflict",
        "Only a machine in maintenance can be set to idle.",
    ),
    RequesterBlocked: (
        status.HTTP_403_FORBIDDEN,
        "requester_blocked",
        "Requester is blocked.",
    ),
    InvalidTransition: (
        status.HTTP_409_CONFLICT,
        "invalid_transition",
        "Invalid request transition.",
    ),
    EventInvalidTransition: (
        status.HTTP_409_CONFLICT,
        "invalid_transition",
        "Invalid event transition.",
    ),
    UseSeriesCollaborators: (
        status.HTTP_409_CONFLICT,
        "use_series_collaborators",
        "Manage projected collaborators on the event series.",
    ),
    FeedbackConflict: (
        status.HTTP_409_CONFLICT,
        "feedback_conflict",
        "Feedback was already submitted with different answers.",
    ),
    FeedbackIneligible: (
        status.HTTP_404_NOT_FOUND,
        "feedback_not_found",
        "Feedback eligibility could not be verified.",
    ),
    BookingInvalidTransition: (
        status.HTTP_409_CONFLICT,
        "invalid_transition",
        "Invalid booking transition.",
    ),
    BookingConflict: (
        status.HTTP_409_CONFLICT,
        "booking_conflict",
        "This space is already booked for that time.",
    ),
    CapacityConflict: (
        status.HTTP_409_CONFLICT,
        "capacity_conflict",
        "Event capacity conflicts with confirmed registrations.",
    ),
    RegistrationClosed: (
        status.HTTP_409_CONFLICT,
        "registration_closed",
        "Registration for this event is closed.",
    ),
    RegistrationRejected: (
        status.HTTP_409_CONFLICT,
        "registration_rejected",
        "This registration application was rejected.",
    ),
    DuplicateRegistration: (
        status.HTTP_400_BAD_REQUEST,
        "duplicate_registration",
        "A registration already exists for this email.",
    ),
    InsufficientStock: (
        status.HTTP_409_CONFLICT,
        "insufficient_stock",
        "Insufficient stock.",
    ),
    ServiceInvalidTransition: (
        status.HTTP_409_CONFLICT,
        "service_invalid_transition",
        "Invalid machine service request transition.",
    ),
    ServiceMachineUnavailable: (
        status.HTTP_409_CONFLICT,
        "service_machine_unavailable",
        "Machine is unavailable for service.",
    ),
    ServiceInsufficientStock: (
        status.HTTP_400_BAD_REQUEST,
        "service_insufficient_stock",
        "Insufficient stock for machine service consumption.",
    ),
    ServiceConsumptionInvalid: (
        status.HTTP_400_BAD_REQUEST,
        "service_consumption_invalid",
        "Invalid machine service consumption.",
    ),
    RequestValidationError: (
        status.HTTP_400_BAD_REQUEST,
        "validation_error",
        "Invalid request.",
    ),
    ReturnValidationError: (
        status.HTTP_400_BAD_REQUEST,
        "return_validation_error",
        "Invalid return.",
    ),
    BoxValidationError: (
        status.HTTP_400_BAD_REQUEST,
        "box_validation_error",
        "Invalid box.",
    ),
    BoxUnavailable: (
        status.HTTP_409_CONFLICT,
        "box_unavailable",
        "Box is already out on another loan.",
    ),
    EvidenceNotUploaded: (
        status.HTTP_409_CONFLICT,
        "evidence_not_uploaded",
        "Evidence has not been uploaded.",
    ),
    DepositRequired: (
        status.HTTP_409_CONFLICT,
        "deposit_required",
        "The loan deposit must be settled before issue.",
    ),
    StorageUnavailable: (
        status.HTTP_503_SERVICE_UNAVAILABLE,
        "evidence_storage_unavailable",
        "Evidence storage is unavailable.",
    ),
}


#: The domain errors the handler below maps to a typed response (they are not APIExceptions); a batch
#: that runs several rows needs them to name the failing id instead of surfacing the first one bare.
WORKFLOW_ERRORS = tuple(_EXCEPTION_MAP)


def workflow_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if getattr(exc, "makerspace_id", None) and getattr(exc, "code", "").endswith("_quota_reached"):
        # Decision 284: the refusing transaction has rolled back by now, so the managers' notice sticks.
        from apps.managed_hosting.space_quotas import tell_managers
        tell_managers(exc)
    if response is not None:
        return add_error_code(exc, outsider_refusal(response, context))

    for exc_type, (status_code, code, default_detail) in _EXCEPTION_MAP.items():
        if isinstance(exc, exc_type):
            detail = str(exc) or default_detail
            return outsider_refusal(Response(
                {"detail": detail, "code": code},
                status=status_code,
            ), context)

    return None
