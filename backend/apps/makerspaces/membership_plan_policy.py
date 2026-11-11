"""Per-plan admission overrides on top of the space policy (G16, X6, X8, X9; decision 71).

A plan may override the space's join mode, payment timing, application form, joining fee
and rejoin rule; a null override inherits. `plan_policy` returns an UNSAVED copy of the
space settings with the plan's overrides applied, so every existing admission gate keeps
reading one `policy` object. The space's own "closed" switch stays the master: a closed
space is closed for every plan (`ensure_join_allowed` refuses before any plan is read).
"""
from django.utils.translation import gettext
import copy
from decimal import Decimal

from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.makerspaces.models_membership_rules import RejoinRule

ZERO = Decimal("0.00")


def _refuse_save(*args, **kwargs):
    raise RuntimeError("A per-plan admission policy is a read-only view; save the space settings instead.")


def plan_policy(makerspace, plan, base=None):
    from apps.makerspaces.membership_admission_settings import settings_for
    base = base if base is not None else settings_for(makerspace)
    if plan is None or getattr(base, "_plan_applied", False):
        return base
    policy = copy.copy(base)
    policy.save = _refuse_save
    policy._plan_applied = True
    if plan.join_mode:
        policy.join_mode = plan.join_mode
    if plan.payment_timing:
        policy.payment_timing = plan.payment_timing
    if plan.application_schema:
        policy.application_schema = plan.application_schema
    return policy


def listed_plans(makerspace):
    from apps.makerspaces.models import MembershipPlan
    return MembershipPlan.objects.filter(makerspace=makerspace, is_public=True, is_active=True,
                                         archived_at__isnull=True).order_by("sort_order", "name", "pk")


def choose_plan(makerspace, policy, plan_id):
    """The plan an applicant asked for (it must be publicly listed), else the default."""
    if plan_id in (None, ""):
        return policy.default_plan
    plan = listed_plans(makerspace).filter(pk=plan_id).first()
    if plan is None:
        raise ValidationError({"plan_id": gettext("Choose one of this makerspace's listed plans.")})
    return plan


def fee_rule(policy, plan):
    if plan is not None and plan.rejoin_rule:
        return plan.rejoin_rule, plan.rejoin_after_days
    return policy.rejoin_dues_rule, getattr(policy, "rejoin_after_days", None)


def fee_amount(policy, plan):
    """`(amount, currency)` of the joining fee before the rejoin rule is applied."""
    if plan is not None and plan.joining_fee is not None:
        return plan.joining_fee, plan.currency
    return policy.joining_fee, policy.joining_fee_currency


def last_covered(makerspace, user):
    """When this person's previous membership here last covered them, or None."""
    from apps.makerspaces.models import MakerspaceMembership, MembershipTerm
    membership = MakerspaceMembership.objects.filter(makerspace=makerspace, user=user).first()
    if membership is None:
        return None
    ends = list(MembershipTerm.objects.filter(membership=membership).exclude(status="cancelled")
                .order_by("-ends_at").values_list("ends_at", flat=True)[:1])
    candidates = [value for value in (*ends, membership.revoked_at) if value is not None]
    return max(candidates) if candidates else None


def joining_fee_for(makerspace, policy, plan, user, *, rejoining, now=None):
    """`(fee, currency)` a joiner owes under the effective rule (see `RejoinRule`)."""
    amount, currency = fee_amount(policy, plan)
    rule, days = fee_rule(policy, plan)
    if amount <= 0 or rule == RejoinRule.NEVER:
        return ZERO, currency
    if not rejoining or rule == RejoinRule.EACH_JOIN:
        return amount, currency
    if rule == RejoinRule.AFTER_LAPSE:
        covered = last_covered(makerspace, user)
        away = (now or timezone.now()) - covered if covered else None
        return (amount, currency) if away is None or away.days > (days or 0) else (ZERO, currency)
    return ZERO, currency


def public_schema(schema):
    """The application form as a member sees it: staff-only questions removed (X9).

    A v2 question with `"visibility": "server"` is staff-only for membership forms: it is
    never sent to the public join page or back to the member, and never accepted from them.
    """
    if not isinstance(schema, dict):
        return schema
    questions = [q for q in schema.get("questions", []) if q.get("visibility") != "server"]
    if not schema.get("sections"):
        return {**schema, "questions": questions}
    from apps.forms_schema.schema_items_static import reanchor_sections
    return {**schema, "questions": questions, "sections": reanchor_sections(schema, questions)}


def staff_only_questions(schema):
    if not isinstance(schema, dict):
        return []
    return [q for q in schema.get("questions", []) if q.get("visibility") == "server"]


def sync_plan_features(makerspace):
    """Dependency completion (#87) for per-plan overrides: a plan that uses vouching or
    its own application form switches the matching membership feature on. Add-only:
    the space settings editor owns switching them off. Caller holds the space lock."""
    from apps.makerspaces.membership_admission_settings import plan_feature_needs
    vouch, form = plan_feature_needs(makerspace)
    features = set(makerspace.enabled_features or [])
    wanted = {key for key, needed in (("membership.vouching", vouch), ("membership.application_form", form))
              if needed}
    if wanted - features:
        makerspace.enabled_features = sorted(features | wanted)
        makerspace.save(update_fields=["enabled_features"])
