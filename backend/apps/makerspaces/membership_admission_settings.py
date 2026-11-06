"""Admission policy compatibility and audited settings updates."""
from django.utils.translation import gettext
from django.db import transaction
from rest_framework.exceptions import APIException, PermissionDenied, ValidationError

from apps.accounts import rbac
from apps.audit import services as audit
from apps.makerspaces.guards import require_module_locked
from apps.makerspaces.models import MakerspaceMembershipSettings
from apps.makerspaces.platform import feature_enabled, module_enabled
from apps.payments.availability import charge_tracking_enabled


class AdmissionError(APIException):
    status_code = 400

    def __init__(self, code, detail):
        super().__init__({"code": code, "detail": detail}, code=code)


RECIPES = {
    "free_open": {"join_mode": "open", "payment_timing": "after_activation"},
    "free_vouch": {"join_mode": "vouch", "payment_timing": "after_activation"},
    "paid_approval": {"join_mode": "approval", "payment_timing": "before_activation"},
    "paid_invite_only": {"join_mode": "invite_only", "payment_timing": "before_activation"},
    "closed": {"join_mode": "closed", "payment_timing": "after_activation"},
}


def settings_for(makerspace):
    row = MakerspaceMembershipSettings.objects.filter(makerspace=makerspace).first()
    if row is None:
        row = MakerspaceMembershipSettings(makerspace=makerspace)
    if not row.configured:
        # Legacy writes keep working until admission is explicitly configured.
        row.join_mode = {"request": "approval"}.get(makerspace.membership_policy, makerspace.membership_policy)
        row.joining_fee = makerspace.membership_dues_amount
        from apps.payments.models import MakerspacePaymentSettings
        row.joining_fee_currency = MakerspacePaymentSettings.objects.filter(
            makerspace=makerspace,
        ).values_list("default_currency", flat=True).first() or "usd"
    return row


def ensure_join_allowed(makerspace):
    row = settings_for(makerspace)
    if module_enabled(makerspace, "membership") and row.join_mode == "closed":
        raise AdmissionError("membership_closed", "This makerspace is closed to new memberships.")
    return row


def application_schema_for(makerspace, policy):
    return policy.application_schema if feature_enabled(makerspace, "membership.application_form") else None


def vouching_on(makerspace, policy):
    return policy.join_mode == "vouch" and feature_enabled(makerspace, "membership.vouching")


def validate_policy(makerspace, row):
    plan = row.default_plan
    if plan and (plan.makerspace_id != makerspace.pk or not plan.is_active):
        raise ValidationError({"default_plan": gettext("Choose an active plan in this makerspace.")})
    if plan and row.joining_fee > 0 and plan.currency != row.joining_fee_currency:
        raise ValidationError({"joining_fee_currency": gettext("Joining fee and plan must use the same currency.")})
    paid = row.joining_fee > 0 or (plan is not None and plan.amount > 0)
    if paid and row.payment_timing == "before_activation" and not charge_tracking_enabled(makerspace, "membership"):
        raise ValidationError({"payment_timing": gettext("Pay before activation requires membership charge tracking.")})


def plan_feature_needs(makerspace):
    """Whether any live plan uses vouching or its own application form (per-plan overrides)."""
    from apps.makerspaces.models import MembershipPlan
    plans = MembershipPlan.objects.filter(makerspace=makerspace, is_active=True, archived_at__isnull=True)
    return (plans.filter(join_mode="vouch").exists(),
            plans.filter(application_schema__isnull=False).exclude(application_schema={}).exists())


def sync_legacy_settings(actor, makerspace, values):
    """Keep established PATCH fields writable after opting in to admission settings."""
    if not module_enabled(makerspace, "membership") or not settings_for(makerspace).configured:
        return
    aliases = {}
    if "membership_policy" in values:
        aliases["join_mode"] = {"request": "approval"}.get(values["membership_policy"], values["membership_policy"])
    if "membership_dues_amount" in values:
        aliases["joining_fee"] = values["membership_dues_amount"]
    if aliases:
        update_settings(actor, makerspace, aliases)
        makerspace.refresh_from_db()


def update_settings(actor, makerspace, values):
    with transaction.atomic():
        makerspace = require_module_locked(makerspace, "membership")
        if not rbac.can(actor, rbac.Action.MANAGE_MAKERSPACE, makerspace.pk):
            raise PermissionDenied()
        from apps.makerspaces.membership_admission_settings_l4 import authorize_settings, record_settings
        decisions = authorize_settings(actor, makerspace, values)
        row = settings_for(makerspace)
        from apps.makerspaces.membership_admission_settings_l4 import gate_settings
        gate_settings(makerspace, values, row)
        before = {key: getattr(row, key, None) for key in values}
        values = dict(values)
        recipe = values.pop("recipe", None)
        if recipe:
            defaults = {"default_plan": None, "joining_fee": 0, "application_schema": None,
                        "vouches_required": 1, "voucher_min_tenure_days": 30,
                        "voucher_pending_limit": 3, "vouch_replaces_approval": False}
            defaults.update(RECIPES[recipe])
            defaults.update(values)
            values = defaults
        for name, value in values.items():
            setattr(row, name, value)
        if row.rejoin_dues_rule != "after_lapse":
            row.rejoin_after_days = None
        row.configured = True
        validate_policy(makerspace, row)
        row.full_clean()
        row.save()
        # The settings editor opts in to these gates. Later disabling a feature makes
        # its stored configuration inert, just like every other module feature.
        features = set(makerspace.enabled_features or [])
        plan_vouch, plan_form = plan_feature_needs(makerspace)
        for key, enabled in (("membership.vouching", row.join_mode == "vouch" or plan_vouch),
                             ("membership.application_form", bool(row.application_schema) or plan_form)):
            if enabled:
                features.add(key)
            else:
                features.discard(key)
        makerspace.enabled_features = sorted(features)
        # Legacy clients see the nearest representable mode and the joining fee.
        makerspace.membership_policy = row.join_mode if row.join_mode in ("open", "invite_only") else "request"
        makerspace.membership_dues_amount = row.joining_fee
        makerspace.save(update_fields=["enabled_features", "membership_policy", "membership_dues_amount"])
        audit.record(actor, "membership.admission_settings_updated", makerspace=makerspace,
                     target=row, meta={"fields": sorted(values), "recipe": recipe})
        record_settings(actor, makerspace, before, row, decisions)
    return row
