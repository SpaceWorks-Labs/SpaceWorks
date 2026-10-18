"""Explicit prospective receipt-retention changes, callable by G's settings seam."""
from django.db import transaction
from apps.audit.services import record
from apps.encryption.account_write_fence import account_fences
from apps.makerspaces.models import Makerspace
from apps.tenant_migration.gate_runtime import boundary_tenant_write
from .authority import authorize
from .cleanup_models import FinanceRetentionPolicy, FinanceRetentionPolicyRevision
from .transactions import lock_finance_authority
from .wire import fingerprint
from .validation import closed, reason_code
from .errors import require


def revise(*, request, makerspace_id, data):
    closed(data, ("operation_id", "expected_version", "receipt_days", "reason_code"))
    require(type(data["receipt_days"]) is int and 1 <= data["receipt_days"] <= 36500, "invalid_retention_policy", status=400)
    require(type(data["expected_version"]) is int and data["expected_version"] >= 0, "stale_version", status=400)
    reason_code(data["reason_code"])
    require(request.headers.get("Idempotency-Key") == str(data["operation_id"]), "idempotency_key_mismatch", status=400)
    space = Makerspace.objects.get(pk=makerspace_id)
    authorize(request, space, mutation=True)
    digest = fingerprint({"makerspace_id": makerspace_id, "policy": data})
    with boundary_tenant_write(space.pk), transaction.atomic(), account_fences((request.user.pk,), (space.pk,)):
        space = Makerspace.objects.select_for_update().get(pk=space.pk)
        request.user = lock_finance_authority(request.user, space)
        authorize(request, space, mutation=True)
        prior = FinanceRetentionPolicyRevision.objects.filter(operation_id=data["operation_id"]).first()
        if prior:
            require(prior.makerspace_id == space.pk and prior.actor_id == request.user.pk
                and prior.command_digest == digest, "idempotency_conflict")
            return {"version": prior.policy_version, "receipt_days": prior.receipt_days}
        policy = FinanceRetentionPolicy.objects.select_for_update().filter(makerspace=space).first()
        require(data["expected_version"] == (policy.version if policy else 0), "stale_version")
        # Version one is the implicit deployed 2555-day default already stamped
        # on existing files, even before a host stores its first explicit policy.
        version = policy.version + 1 if policy else 2
        if policy is None:
            policy = FinanceRetentionPolicy(makerspace=space)
        old_days = policy.receipt_days
        policy.receipt_days, policy.version = data["receipt_days"], version
        policy.save()
        FinanceRetentionPolicyRevision.objects.create(makerspace=space, policy_version=version,
            receipt_days=policy.receipt_days, actor=request.user, operation_id=data["operation_id"],
            command_digest=digest, reason_code=data["reason_code"])
        record(request.user, "finance.retention_policy.changed", makerspace=space, target=policy,
            meta={"version": version, "old_days": old_days, "new_days": policy.receipt_days, "reason_code": data["reason_code"]})
        return {"version": version, "receipt_days": policy.receipt_days}
