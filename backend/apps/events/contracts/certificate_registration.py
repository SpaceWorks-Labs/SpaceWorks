"""C verified work and D current awards feed E's sole issuance service."""

from apps.encryption.account_write_fence import assert_account_fence_held
from apps.events.contracts.providers import LockedContext
from apps.events.contributions.models_roles import EventRoleAssignment
from apps.events.contributions.certificate_subjects import resolve
from apps.events.certificates.subjects import EligibleSubject, install_eligibility
from apps.events.judging.provider_subjects import award_eligible


def role_eligible(*, event_id, assignment_id, kind):
    from django.db import connection
    from django.shortcuts import get_object_or_404
    from apps.events.credentials.errors import ProgrammeConflict
    from apps.accounts.models import User
    role = get_object_or_404(EventRoleAssignment, event_id=event_id, pk=assignment_id)
    if not connection.in_atomic_block:
        raise RuntimeError("Contribution eligibility requires the event transaction.")
    from apps.encryption.write_fence import assert_mapped_write_allowed
    assert_mapped_write_allowed(role.makerspace_id)
    if kind != {"volunteer": "volunteer_thanks", "mentor": "mentor_thanks", "judge": "judge_thanks"}.get(role.role):
        raise ProgrammeConflict("Certificate kind does not match the role.", code="certificate_ineligible")
    # An actor fence is not a recipient fence. Missing E scopes refuse here.
    assert_account_fence_held(role.member_id)
    if role.role == "volunteer":
        from apps.events.programme_locks import current_locks
        resolve(event_id=event_id, assignment_id=assignment_id, locks=current_locks(event_id))
    else:
        if role.state not in ("approved", "completed") or role.imported_inert:
            raise ProgrammeConflict("Completed contribution evidence is required.", code="certificate_ineligible")
        if role.role == "mentor":
            from apps.events.mentoring.models_rounds import MentorRoundCheckin
            worked = MentorRoundCheckin.objects.filter(event_id=event_id, mentor=role,
                round__practice_run_id=None, away=False).exists()
        else:
            from apps.events.judging.models_scoring import JudgeScore, JudgeRankingBallot
            worked = JudgeScore.objects.filter(event_id=event_id, assignment__judge_role_assignment=role,
                submitted_at__isnull=False).exists() or JudgeRankingBallot.objects.filter(
                    event_id=event_id, judge=role).exists() or _compared(event_id, role)
        if not worked:
            raise ProgrammeConflict("Completed contribution evidence is required.", code="certificate_ineligible")
    member = User.objects.get(pk=role.member_id)
    from apps.events.contributions.commands import active_member
    active_member(member)
    return EligibleSubject("role_assignment", role.pk, event_id, role.member_id,
                           member.display_name or member.get_full_name() or member.username)


def _compared(event_id, role):
    from apps.events.judging.models_pairwise import JudgePairwiseComparison
    return JudgePairwiseComparison.objects.filter(event_id=event_id, judge=role, invalidation__isnull=True
                                                  ).exclude(outcome="skip").exists()


def install():
    install_eligibility(roles=role_eligible, awards=award_eligible)
