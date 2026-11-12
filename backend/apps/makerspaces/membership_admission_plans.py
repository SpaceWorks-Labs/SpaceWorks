"""Which plan a join request is for, and which join gates apply to it (X8, X11).

Called by `request_membership` under the makerspace lock. The applicant may choose any
publicly listed plan (else the space's default plan applies, as before). An invite link
admits its holder through the invitation gate and may preselect the plan. The plan's own
join mode then decides: closed refuses, invite-only needs a link, open auto-approves,
approval waits for staff, vouch collects vouches -- exactly the space modes, per plan.
"""
from django.utils.translation import gettext
from apps.makerspaces.membership_admission_settings import AdmissionError
from apps.makerspaces.membership_plan_policy import choose_plan, plan_policy


def resolve_join(makerspace, user, policy, plan_id, invite_code):
    from apps.makerspaces.membership_features import membership_feature_on
    if plan_id not in (None, "") and not membership_feature_on(makerspace, "public_plans"):
        raise AdmissionError("membership_plan_choice_unavailable", gettext("This makerspace does not offer a choice of plan."))
    if invite_code and not membership_feature_on(makerspace, "admission_tools"):
        raise AdmissionError("membership_invite_link_invalid", gettext("This invite link is not valid."))
    link = None
    if invite_code:
        from apps.makerspaces.membership_invite_links import redeem_locked
        link = redeem_locked(makerspace, invite_code, actor=user)
    if link is not None and link.plan_id and link.plan.is_active and link.plan.archived_at is None:
        plan = link.plan
    else:
        plan = choose_plan(makerspace, policy, plan_id)
    effective = plan_policy(makerspace, plan, policy)
    if effective.join_mode == "closed":
        raise AdmissionError("membership_plan_closed", gettext("This plan is not taking new members."))
    if effective.join_mode == "invite_only" and link is None:
        raise AdmissionError("membership_invite_required", gettext("This makerspace is invite-only."))
    return plan, effective
