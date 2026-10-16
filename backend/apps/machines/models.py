from .models_materials import MachineMaterial  # noqa: F401

# Service-request models are kept separate so the long-lived machine catalog stays
# compact; importing here preserves the app's established public model surface.
from .models_service import (
    MachineConsumableAdjustment,
    MachineConsumablePool,
    MachineServiceRequest,
    ServiceBucket,
    ServiceQueue,
    ServiceRequestConsumption,
    ServiceRequestFile,
    get_or_create_default_bucket,
)
# Training/certification records. String FK references throughout, so import order
# relative to MachineType below does not matter.
from .models_certifications import CertificationGrant, CertificationType
from .models_policy import MakerspaceMachineTypePolicy
from .printing_cutover_models import PrintingCutoverRepair, PrintingCutoverState

# Per-membership type scope links. String FK references make import order independent
# of the MachineType/Machine declarations below.
from .models_membership_scope import MembershipMachineTypeScope
from .models_catalog import (
    Machine,
    MachineOperator,
    MachineType,
    MakerspaceMachineTypePricing,
)
from .models_usage import (
    MachineConsumable,
    MachineDocument,
    MachineErrorLog,
    MachineUsageEntry,
    MachineUsageEntryQuerySet,
)

__all__ = [
    "CertificationGrant",
    "CertificationType",
    "Machine",
    "MachineConsumable",
    "MachineConsumableAdjustment",
    "MachineConsumablePool",
    "MachineDocument",
    "MachineErrorLog",
    "MachineOperator",
    "MachineServiceRequest",
    "MachineType",
    "MembershipMachineTypeScope",
    "MachineUsageEntry",
    "MachineUsageEntryQuerySet",
    "MakerspaceMachineTypePricing",
    "MakerspaceMachineTypePolicy",
    "PrintingCutoverRepair",
    "PrintingCutoverState",
    "ServiceBucket",
    "ServiceQueue",
    "ServiceRequestConsumption",
    "ServiceRequestFile",
    "get_or_create_default_bucket",
]
