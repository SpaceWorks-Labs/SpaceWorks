"""Query-free retention provider. G composes this into its literal shared maps."""
from dataclasses import dataclass
from . import purge, portable, object_capture


@dataclass(frozen=True)
class ReimbursementRetentionProvider:
    key: str = "event_reimbursements"
    preflight = staticmethod(purge.preflight)
    delete = staticmethod(purge.delete)
    delete_domain_for_tenant = staticmethod(purge.delete_domain_for_tenant)
    transform = staticmethod(portable.transform)
    capture = staticmethod(object_capture.capture)


RETENTION_PROVIDER = ReimbursementRetentionProvider()


def module_purge_plan():
    from apps.makerspaces.module_purge_plans import ModulePurgePlan
    return ModulePurgePlan("event_reimbursements", "Terminal travel-support history; core liabilities and receipts survive.",
        purge.delete, pii_labels=tuple("event_reimbursements." + name for name in portable.PII_FIELDS),
        private_keys=object_capture.module_private_keys, private_key_sizes=object_capture.module_private_key_sizes)
