"""Finance creates policy and its initial fund atomically; PATCH never upserts."""
from datetime import timedelta
from django.utils import timezone
from apps.events.programme.commands import fingerprint
from apps.payments.currencies import normalize_supported_currency
from apps.payments.event_payouts.errors import require
from apps.payments.event_payouts.validation import minor
from .config_models import ReimbursementProgramme
from .budget_models import ReimbursementBudgetPool
from .budget_service import fund_locked
from .transactions import command, changed
from .policy import POLICY_FIELDS, validate_policy


def create_or_get(*, request, event_id, data):
    currency = normalize_supported_currency(data["currency"])
    minor(data["initial_total_minor"], zero=True)
    with command(event_id=event_id, actor=request.user, request=request, data=data,
                 action="programme.initialize", finance=True) as ctx:
        if ctx.replay:
            return ctx.replay
        require(data["expected_version"] == 0, "stale_version")
        defaults = {name: ReimbursementProgramme._meta.get_field(name).get_default() for name in POLICY_FIELDS}
        defaults["claim_due_at"] = ctx.event.ends_at + timedelta(days=30)
        settings = validate_policy({**defaults, **data["initial_settings"]}, event=ctx.event)
        require(settings["enabled"] is False, "programme_must_start_disabled", status=400)
        initialization_digest = fingerprint({"currency": currency, "initial_total_minor": data["initial_total_minor"],
                                             "initial_settings": settings})
        existing = ReimbursementProgramme.objects.select_for_update().filter(event=ctx.event).first()
        if existing:
            require(existing.initialization_digest == initialization_digest, "programme_initialization_conflict")
            pool = ReimbursementBudgetPool.objects.get(programme=existing, currency=existing.currency, audience="participants")
            return ctx.finish(existing, created=False, pool_id=pool.pk, pool_version=pool.version)
        require("claim_due_at" in settings, "claim_due_at_required", status=400)
        row = ReimbursementProgramme.objects.create(event=ctx.event, currency=currency, created_by=ctx.actor,
            approved_by=ctx.actor, initialization_operation_id=data["operation_id"],
            initialization_digest=initialization_digest, **settings)
        pool = ReimbursementBudgetPool.objects.create(programme=row, currency=currency)
        fund_locked(pool, data["initial_total_minor"], operation_id=data["operation_id"], actor=ctx.actor,
                    reason_code="initial_funding")
        # Creation's initial funding is part of version one, not a later edit.
        pool.version = 1
        pool.save(update_fields=["version"])
        ctx.audit("event.reimbursement.programme_initialized", row, pool_id=pool.pk)
        return ctx.finish(row, created=True, pool_id=pool.pk, pool_version=pool.version)


def configure(*, request, event_id, data):
    minor(data["budget_delta_minor"], signed=True)
    with command(event_id=event_id, actor=request.user, request=request, data=data,
                 action="programme.configure", finance=True) as ctx:
        if ctx.replay:
            return ctx.replay
        row = ReimbursementProgramme.objects.select_for_update().filter(event=ctx.event).first()
        require(row is not None, "programme_not_initialized")
        pool = ReimbursementBudgetPool.objects.select_for_update().get(pk=data["pool_id"], programme=row)
        ctx.cas(row)
        require(pool.version == data["expected_pool_version"] and row.finance_policy_revision == data["policy_revision"], "stale_version")
        combined = {name: getattr(row, name) for name in POLICY_FIELDS}
        # A client that only knows the legacy yes/no switch must not be overridden by the stored
        # ``required_submission`` (G11): drop the stored pair so the switch derives it, then persist both.
        legacy_only = "require_project_submission" in data["settings"] and "required_submission" not in data["settings"]
        if legacy_only:
            combined.pop("required_submission", None)
            combined.pop("required_submission_stage", None)
        normalized = validate_policy({**combined, **data["settings"]}, event=ctx.event)
        settings = {key: normalized[key] for key in data["settings"]}
        if legacy_only:
            settings.update(required_submission=normalized["required_submission"],
                            required_submission_stage=normalized["required_submission_stage"])
        if row.imported_paused:
            require(data.get("reconciliation_confirmed") is True, "finance_reconciliation_required")
            from django.db.models import Sum
            totals = pool.reservations.aggregate(held=Sum("held_minor"), committed=Sum("committed_minor"))
            require((totals["held"] or 0, totals["committed"] or 0) == (pool.reserved_minor, pool.committed_minor),
                    "budget_reconciliation_required")
        fund_locked(pool, data["budget_delta_minor"], operation_id=data["operation_id"], actor=ctx.actor,
                    reason_code=data["reason_code"])
        changed(row, **settings, imported_paused=False, finance_policy_revision=row.finance_policy_revision + 1)
        ctx.audit("event.reimbursement.programme_configured", row, pool_id=pool.pk, policy_revision=row.finance_policy_revision)
        if data["budget_delta_minor"] > 0:
            from .notices import reviewer_preview_locked
            reviewer_preview_locked(ctx, pool)
        return ctx.finish(row, pool_id=pool.pk, pool_version=pool.version)
