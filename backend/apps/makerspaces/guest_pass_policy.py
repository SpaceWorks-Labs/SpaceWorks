"""Decision 223: the guest-pass switches, the per-space policy and the frozen entitlements.

`guest_passes_on` is the one question every enforcement path asks first: with the
`membership` module or `membership.guest_passes` off, a pass stops unlocking anything
(decision 218: "off removes it everywhere"); recorded passes, loans and charges keep their
normal return and settlement paths.
"""
from django.db import transaction
from rest_framework.exceptions import APIException, ValidationError

from apps.audit import services as audit
from apps.makerspaces.membership_features import membership_feature_on
from apps.makerspaces.models import GuestPassPolicy

POLICY_FIELDS = (
    "guest_borrowing_mode", "guest_machine_mode", "sponsored_liability", "walk_in_registration_creates",
    "waiver_required_on_site", "waiver_gate_without_passes", "sponsor_min_tenure_days", "max_concurrent_guests_per_sponsor",
    "sponsor_must_be_present", "visits_before_join_prompt", "hard_visit_cap", "day_pass_daily_cap",
)


class GuestPassError(APIException):
    """A refusal with a stable machine code (`guest_pass_no_borrow`, `sponsor_limit`, ...)."""

    status_code = 400

    def __init__(self, code, detail, status_code=None):
        if status_code is not None:
            self.status_code = status_code
        self.error_code = code
        super().__init__({"code": code, "detail": detail}, code=code)


def guest_passes_on(makerspace):
    return membership_feature_on(makerspace, "guest_passes")


def day_passes_on(makerspace):
    return guest_passes_on(makerspace) and membership_feature_on(makerspace, "day_passes")


def policy_for(makerspace):
    return GuestPassPolicy.for_makerspace(makerspace)


def frozen_entitlements(policy, template=None):
    """The snapshot written onto a pass. A product's template may only NARROW the space policy."""
    borrow, machines = policy.guest_borrowing_mode, policy.guest_machine_mode
    template = template or {}
    if template.get("borrow") == "none":
        borrow = "none"
    if template.get("machines") == "none":
        machines = "none"
    return {"presence": True, "borrow": borrow, "machines": machines}


def policy_payload(policy):
    return {name: getattr(policy, name) for name in POLICY_FIELDS}


def update_policy(actor, makerspace, data):
    """Space Manager edit (the view checks manage_makerspace). Audited with the changed field NAMES only."""
    unknown = set(data) - set(POLICY_FIELDS)
    if unknown:
        raise ValidationError({name: "Unknown setting." for name in sorted(unknown)})
    with transaction.atomic():
        policy = GuestPassPolicy.objects.select_for_update().filter(makerspace=makerspace).first()
        policy = policy or GuestPassPolicy(makerspace=makerspace)
        changed = []
        for name, value in data.items():
            if getattr(policy, name) != value:
                setattr(policy, name, value)
                changed.append(name)
        policy.updated_by = actor
        policy.full_clean(exclude=["updated_by"])
        policy.save()
        if changed:
            audit.record(actor, "makerspace.guest_pass_policy_updated", makerspace=makerspace, target=policy,
                         meta={"fields": sorted(changed)})
    return policy
