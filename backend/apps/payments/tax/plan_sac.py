"""A membership plan's own SAC code on the GST snapshot (parity O-B3, `billing.plan_sac`).

The space-wide SAC (`MakerspaceTaxSettings.sac_code`, default 999599) is frozen onto every GST charge. When a
plan carries its own 4-8 digit code and the switch is on, the charge a membership TERM raises freezes that
code instead, so the invoice and the GSTR-1 HSN summary show the plan's code. Frozen at raise time, like the
rest of the snapshot: changing the plan later never rewrites a charge or a document already issued.
"""

import re

from django.utils.translation import gettext

from apps.makerspaces.platform import feature_enabled

SAC = re.compile(r"^\d{4,8}$")


def validate_plan_sac(value):
    """The normalised code, or a ValueError the serializer turns into a 400."""
    value = (value or "").strip()
    if value and not SAC.fullmatch(value):
        raise ValueError(gettext("A SAC code is 4 to 8 digits."))
    return value


def plan_for_subject(makerspace, subject_type, subject_id):
    from apps.makerspaces.models import MembershipPlan, MembershipRequest, MembershipTerm
    from apps.payments.models import Payment

    kinds = Payment.SubjectType
    if subject_type in (kinds.MEMBERSHIP_TERM, kinds.MEMBERSHIP_TERM_START):
        term = MembershipTerm.objects.filter(pk=subject_id, plan__makerspace=makerspace).select_related("plan").first()
        return term.plan if term else None
    if subject_type == kinds.MEMBERSHIP_REQUEST:
        request = MembershipRequest.objects.filter(pk=subject_id, makerspace=makerspace).first()
        return MembershipPlan.objects.filter(pk=request.selected_plan_id, makerspace=makerspace).first() if (
            request and request.selected_plan_id) else None
    return None


def with_plan_sac(makerspace, subject_type, subject_id, snapshot):
    """The snapshot with the plan's SAC swapped in; the input unchanged when nothing applies."""
    if not snapshot or snapshot.get("mode") != "gst_india" or not feature_enabled(makerspace, "billing.plan_sac"):
        return snapshot
    plan = plan_for_subject(makerspace, subject_type, subject_id)
    if plan is None or not plan.sac_code:
        return snapshot
    return {**snapshot, "sac_code": plan.sac_code}
