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
from .models_access_grants import MachineAccessGrant  # noqa: F401
from .models_induction import EventInductionLink, GuestCertificationGrant  # noqa: F401
from .models_supervised import SupervisedParticipant, SupervisedSession, SupervisedUse  # noqa: F401
from .models_policy import MakerspaceMachineTypePolicy
from .printing_cutover_models import PrintingCutoverRepair, PrintingCutoverState

# Per-membership type scope links. String FK references make import order independent
# of the MachineType/Machine declarations below.
from .models_membership_scope import MembershipMachineScope, MembershipMachineTypeScope
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
    'MachineStatusEvent',
    'ConsumableCostRecord',

    "CertificationGrant",
    "EventInductionLink",
    "GuestCertificationGrant",
    "SupervisedParticipant",
    "SupervisedSession",
    "SupervisedUse",
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
    "MembershipMachineScope",
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

from .models_tracking import MachineStatusEvent, ConsumableCostRecord  # noqa: F401
from .models_job_batch import MachineJobBatch  # noqa: F401,E402
from .models_downtime import MachineDowntime  # noqa: F401,E402
from .models_sessions import MachineSession, MachineSessionAmendment  # noqa: F401,E402
# Decisions 341/343: per-type consumable profiles, their job usage and editable type templates.
from .models_consumable_profiles import (  # noqa: F401,E402
    MachineTypeConsumable, MachineTypeTemplate, ServiceRequestConsumableUsage,
)
# Decision 343 follow-up: per-type booking defaults, training notes and documents in one space.
from .models_type_setup import MachineTypeDocument, MachineTypeSetup  # noqa: F401,E402
