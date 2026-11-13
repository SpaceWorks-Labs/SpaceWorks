"""Shared optional-module check for canonical registration/application bridges."""

from apps.makerspaces.guards import require_module
from apps.makerspaces.platform import module_enabled
from apps.separability.tombstones import app_is_tombstoned


def reimbursement_module_available(makerspace):
    return (
        not app_is_tombstoned("events")
        and not app_is_tombstoned("event_reimbursements")
        and module_enabled(makerspace, "events")
        and module_enabled(makerspace, "event_reimbursements")
    )


def require_reimbursement_module(makerspace):
    require_module(makerspace, "events")
    require_module(makerspace, "event_reimbursements")
