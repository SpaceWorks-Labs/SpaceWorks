"""Decision 223 (k), lane L3b: switches, the per-space policy and the shared refusal type.

Three capabilities, all under `membership`, all off by default, all keeping their data when turned off:
`membership.minors`, `membership.volunteer_credit`, `membership.join_funnel`. Every enforcement path asks
`minors_on` / `volunteer_on` / `funnel_on` first, so a switched-off feature is inert everywhere (decision
218: off removes it everywhere).
"""
from django.db import transaction
from rest_framework.exceptions import APIException, ValidationError

from apps.audit import services as audit
from apps.makerspaces.membership_features import membership_feature_on
from apps.makerspaces.models import CommunityPolicy

MINOR_FIELDS = ("minors_admitted", "minors_minimum_age", "adult_age", "guardian_must_be_present",
                "minors_may_borrow", "minors_may_use_machines", "consent_valid_days")
VOLUNTEER_FIELDS = ("volunteer_minutes_per_credit", "volunteer_credit_kind", "volunteer_credit_amount",
                    "volunteer_credit_days")
FUNNEL_FIELDS = ("join_followup_enabled", "join_followup_delay_hours")
POLICY_FIELDS = MINOR_FIELDS + VOLUNTEER_FIELDS + FUNNEL_FIELDS
_GATES = {"minors": MINOR_FIELDS, "volunteer_credit": VOLUNTEER_FIELDS, "join_funnel": FUNNEL_FIELDS}


class CommunityError(APIException):
    """A refusal with a stable machine code (`guardian_consent_required`, `minor_not_admitted`, ...)."""

    status_code = 403

    def __init__(self, code, detail, status_code=None):
        if status_code is not None:
            self.status_code = status_code
        self.error_code = code
        super().__init__({"code": code, "detail": detail}, code=code)


def minors_on(makerspace):
    return membership_feature_on(makerspace, "minors")


def volunteer_on(makerspace):
    return membership_feature_on(makerspace, "volunteer_credit")


def funnel_on(makerspace):
    return membership_feature_on(makerspace, "join_funnel")


def policy_for(makerspace):
    return CommunityPolicy.for_makerspace(makerspace)


def policy_payload(policy):
    return {name: getattr(policy, name) for name in POLICY_FIELDS}


def update_policy(actor, makerspace, data):
    """Space Manager edit (the view checks manage_makerspace). Changing a field of a switched-off feature is
    refused; the audit entry carries the changed field names only."""
    unknown = set(data) - set(POLICY_FIELDS)
    if unknown:
        raise ValidationError({name: "Unknown setting." for name in sorted(unknown)})
    with transaction.atomic():
        policy = CommunityPolicy.objects.select_for_update().filter(makerspace=makerspace).first()
        policy = policy or CommunityPolicy(makerspace=makerspace)
        changed = []
        for name, value in data.items():
            if getattr(policy, name) != value:
                setattr(policy, name, value)
                changed.append(name)
        for key, names in _GATES.items():
            if any(name in changed for name in names) and not membership_feature_on(makerspace, key):
                raise CommunityError("feature_disabled", f"Turn on membership.{key} to change these settings.")
        policy.updated_by = actor
        policy.full_clean(exclude=["updated_by"])
        policy.save()
        if changed:
            audit.record(actor, "makerspace.community_policy_updated", makerspace=makerspace, target=policy,
                         meta={"fields": sorted(changed)})
    return policy
