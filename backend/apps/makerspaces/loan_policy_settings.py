"""Shared audited loan-policy writer for the settings editor and packs."""
from django.db import transaction

from apps.accounts import rbac
from apps.admin_api.permissions import require_action
from apps.admin_api.serializers_loan_policy import ReturnPolicySerializer
from apps.audit import services as audit
from apps.tenant_migration.gate_runtime import assert_write_allowed
from .guards import require_module_locked
from .models_loan_policy import MakerspaceLoanPolicy
from .settings_authority import assert_setting_write, record_change


@transaction.atomic
def update_loan_policy(actor, makerspace, values):
    assert_write_allowed(makerspace.pk)
    makerspace = require_module_locked(makerspace, "request_workflow")
    # Lending settings belong to the inventory module of the settings-authority layer
    # (#101): the Space Manager always, the Inventory Manager for rental timing without a
    # grant (C-11d) and for the rest with the inventory grant, never past an SM lock.
    if not rbac.can(actor, rbac.Action.EDIT_INVENTORY, makerspace.pk):
        require_action(actor, rbac.Action.MANAGE_MAKERSPACE, makerspace.pk)
    policy = MakerspaceLoanPolicy.for_makerspace(makerspace)
    before = {key: value for key, value in ReturnPolicySerializer(policy).data.items() if key != "id"}
    serializer = ReturnPolicySerializer(policy, data=values, partial=True)
    serializer.is_valid(raise_exception=True)
    changed = [key for key, value in serializer.validated_data.items() if getattr(policy, key, None) != value]
    if "account_self_renewal" in changed:  # Space Manager only (dec 221a): never the inventory grant
        require_action(actor, rbac.Action.MANAGE_MAKERSPACE, makerspace.pk)
    decisions = {key: assert_setting_write(actor, makerspace, "inventory", key) for key in changed}
    policy = serializer.save()
    makerspace.default_loan_days = policy.default_loan_days
    makerspace.save(update_fields=["default_loan_days"])
    audit.record(actor, "makerspace.return_policy_updated", makerspace=makerspace,
                 target=policy, meta={
                     "policy_id": policy.pk,
                     "before": {
                         "default_loan_days": before["default_loan_days"],
                         "loan_renewal_mode": before["loan_renewal_mode"],
                         "loan_max_renewals": before["loan_max_renewals"],
                         "loan_renewal_days": before["loan_renewal_days"],
                         "loan_max_active": before["loan_max_active"],
                         "loan_max_items": before["loan_max_items"],
                         "loan_reminder_offsets_hours": before["loan_reminder_offsets_hours"],
                         "loan_escalate_overdue_days": before["loan_escalate_overdue_days"],
                         "account_self_renewal": before["account_self_renewal"],
                     },
                     "after": {
                         "default_loan_days": serializer.data["default_loan_days"],
                         "loan_renewal_mode": serializer.data["loan_renewal_mode"],
                         "loan_max_renewals": serializer.data["loan_max_renewals"],
                         "loan_renewal_days": serializer.data["loan_renewal_days"],
                         "loan_max_active": serializer.data["loan_max_active"],
                         "loan_max_items": serializer.data["loan_max_items"],
                         "loan_reminder_offsets_hours": serializer.data["loan_reminder_offsets_hours"],
                         "loan_escalate_overdue_days": serializer.data["loan_escalate_overdue_days"],
                         "account_self_renewal": serializer.data["account_self_renewal"],
                     },
                 })
    for key, decision in decisions.items():
        record_change(actor, makerspace, "inventory", key, before.get(key), serializer.data.get(key), decision)
    return policy
