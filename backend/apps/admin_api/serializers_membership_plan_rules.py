"""Validation of the release-2 plan fields (G16, X5, X6, X8, X9; decision 71).

Kept apart from the plan serializer so the shipped validation stays readable. Two
switches gate the new fields (#95): `membership.plan_rules` (type, renewal price and the
per-plan overrides) and `membership.public_plans` (public listing, slug and description).
A write that CHANGES one of them while its switch is off is refused with 403
`feature_disabled`; reads always show the stored values, so switching off loses nothing.
"""
from django.utils.translation import gettext
import re

from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied

from apps.makerspaces.membership_features import membership_feature_on
from apps.makerspaces.models_membership_rules import LateRenewal, PlanType, RejoinRule

RULE_FIELDS = {
    "plan_type": PlanType.ROLLING, "fixed_end_date": None, "renewal_amount": None, "joining_fee": None,
    "rejoin_rule": None, "rejoin_after_days": None, "payment_timing": None, "join_mode": None,
    "application_schema": None, "late_renewal": LateRenewal.BACKDATE,
}
PUBLIC_FIELDS = {"is_public": False, "slug": "", "description": ""}
_SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def _gate(makerspace, attrs, fields, key, instance):
    if makerspace is None or membership_feature_on(makerspace, key):
        return
    # A change is a value that differs from what is stored (or the default on create);
    # re-sending stored values while the switch is off is not refused.
    changed = sorted(name for name, default in fields.items()
                     if name in attrs and attrs[name] != getattr(instance, name, default))
    if changed:
        raise PermissionDenied({"code": "feature_disabled", "feature": f"membership.{key}",
                                "detail": gettext('Turn on membership.{key} to use: {value}.').format(key=key, value=', '.join(changed))})


def validate_plan_rules(attrs, instance, makerspace):
    _gate(makerspace, attrs, RULE_FIELDS, "plan_rules", instance)
    _gate(makerspace, attrs, PUBLIC_FIELDS, "public_plans", instance)

    def value(name):
        return attrs.get(name, getattr(instance, name, RULE_FIELDS.get(name)))

    plan_type = value("plan_type") or PlanType.ROLLING
    if plan_type == PlanType.FIXED_END and not value("fixed_end_date"):
        raise serializers.ValidationError({"fixed_end_date": gettext("A fixed-end plan needs its end date.")})
    if plan_type != PlanType.FIXED_END and value("fixed_end_date") is not None:
        raise serializers.ValidationError({"fixed_end_date": gettext("Only a fixed-end plan takes an end date.")})
    rule = value("rejoin_rule")
    if rule == RejoinRule.AFTER_LAPSE and not value("rejoin_after_days"):
        raise serializers.ValidationError({"rejoin_after_days": gettext("Say how many days without a membership count as a lapse.")})
    if rule != RejoinRule.AFTER_LAPSE and value("rejoin_after_days") is not None:
        raise serializers.ValidationError({"rejoin_after_days": gettext("Only the after-a-lapse rule takes a day count.")})
    slug = attrs.get("slug")
    if slug and not _SLUG.match(slug):
        raise serializers.ValidationError({"slug": gettext("Use lowercase letters, digits and single hyphens.")})
    if plan_type == PlanType.LIFETIME and value("auto_renew"):
        raise serializers.ValidationError({"auto_renew": gettext("A lifetime plan never renews.")})
    return attrs
