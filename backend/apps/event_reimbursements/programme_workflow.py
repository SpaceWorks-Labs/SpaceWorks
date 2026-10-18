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


POLICY_FIELDS = frozenset({"enabled", "request_phase", "request_opens_at", "request_closes_at",
    "award_mode", "tier_rules", "allowed_categories", "exclusions", "min_distance_km",
    "eligible_countries", "eligible_cohorts", "award_accept_days", "claim_due_at", "attendance_required",
    "require_project_submission", "permitted_venue_sources", "category_limits"})


def validate_policy(value, *, event):
    require(isinstance(value, dict) and not set(value) - POLICY_FIELDS, "invalid_programme_settings", status=400)
    require("claim_due_at" not in value or value["claim_due_at"] > event.ends_at, "claim_due_before_event_end", status=400)
    require(value.get("request_phase", "both") in ("application", "after_acceptance", "both"), "invalid_request_phase", status=400)
    require(value.get("award_mode", "need_based") in ("fixed_tier", "route_cap", "percentage", "need_based"),
            "invalid_award_mode", status=400)
    if "allowed_categories" in value:
        categories = value["allowed_categories"]
        require(isinstance(categories, list) and 1 <= len(categories) <= 5
            and len(categories) == len(set(categories)) and set(categories) <=
            {"rail", "air", "bus", "ground_transport", "lodging"}, "invalid_categories", status=400)
    for key in ("enabled", "attendance_required", "require_project_submission"):
        require(key not in value or type(value[key]) is bool, "invalid_programme_settings", status=400)
    for amount in value.get("category_limits", {}).values():
        minor(amount, zero=True)
    return value


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
            pool = ReimbursementBudgetPool.objects.get(programme=existing, currency=existing.currency)
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
    with command(event_id=event_id, actor=request.user, request=request, data=data,
                 action="programme.configure", finance=True) as ctx:
        if ctx.replay:
            return ctx.replay
        row = ReimbursementProgramme.objects.select_for_update().filter(event=ctx.event).first()
        require(row is not None, "programme_not_initialized")
        pool = ReimbursementBudgetPool.objects.select_for_update().get(pk=data["pool_id"], programme=row)
        ctx.cas(row)
        require(pool.version == data["expected_pool_version"] and row.finance_policy_revision == data["policy_revision"], "stale_version")
        settings = validate_policy(data["settings"], event=ctx.event)
        fund_locked(pool, data["budget_delta_minor"], operation_id=data["operation_id"], actor=ctx.actor,
                    reason_code=data["reason_code"])
        changed(row, **settings, finance_policy_revision=row.finance_policy_revision + 1)
        ctx.audit("event.reimbursement.programme_configured", row, pool_id=pool.pk, policy_revision=row.finance_policy_revision)
        return ctx.finish(row, pool_id=pool.pk, pool_version=pool.version)
