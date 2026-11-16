"""Decision 223 (k), lane L3b: the one question every enforcement path asks about a minor.

`require_minor_clearance(user, makerspace, purpose)` is called lazily (one function-local import) from the
admission, registration, guest-pass, presence, borrowing and machine paths. It returns None, silently, when
`membership.minors` is off or the account is not a minor here, so no caller needs its own switch check.

Refusal codes (HTTP 403 unless noted): `minor_not_admitted`, `minor_below_minimum_age`,
`guardian_terms_missing` (409), `guardian_consent_required`, `guardian_consent_expired`,
`guardian_presence_required`, `minor_borrowing_not_allowed`, `minor_machines_not_allowed`.

Presence (auto decision): when the space needs the guardian present, a minor never checks themselves in; staff
at the desk check them in, and that staff check-in is the attestation that the guardian is there. Door access
is not part of this (owner, 2026-11-10).
"""
from django.utils import timezone

from apps.makerspaces.community_policy import CommunityError, minors_on, policy_for
from apps.makerspaces.minors import active_terms, age_of, current_consent, is_minor, profile_for
from apps.makerspaces.models import GuardianConsent

PURPOSES = ("membership", "event", "guest_pass", "presence", "borrow", "machine")


def _consent_code(profile, makerspace):
    if active_terms(makerspace) is None:
        return "guardian_terms_missing", "This space has not published guardian consent terms yet.", 409
    if GuardianConsent.objects.filter(profile=profile).exists():
        return ("guardian_consent_expired",
                "The guardian's consent has expired, been withdrawn, or was given for older terms.", 403)
    return "guardian_consent_required", "A guardian must sign the consent before this person can take part.", 403


def evaluate(user, makerspace, purpose, *, staff_present=False, now=None):
    """`(code, detail, status)` for the first reason the minor may not do this, or None when allowed."""
    if user is None or not minors_on(makerspace):
        return None
    profile = profile_for(makerspace, user)
    policy = policy_for(makerspace)
    if not is_minor(profile, policy):
        return None
    if not policy.minors_admitted:
        return "minor_not_admitted", "This space does not admit people under the age of majority.", 403
    age = age_of(profile)
    if age is not None and age < policy.minors_minimum_age:
        return "minor_below_minimum_age", "This person is under the minimum age for this space.", 403
    if current_consent(profile, now or timezone.now()) is None:
        return _consent_code(profile, makerspace)
    if purpose == "presence" and policy.guardian_must_be_present and not staff_present:
        return "guardian_presence_required", "A guardian must be present: ask staff at the desk to check in.", 403
    if purpose == "borrow" and not policy.minors_may_borrow:
        return "minor_borrowing_not_allowed", "This space does not lend to people under the age of majority.", 403
    if purpose == "machine" and not policy.minors_may_use_machines:
        return "minor_machines_not_allowed", "This space does not let people under the age of majority use machines.", 403
    return None


def require_minor_clearance(user, makerspace, purpose, *, staff_present=False, now=None):
    refusal = evaluate(user, makerspace, purpose, staff_present=staff_present, now=now)
    if refusal is not None:
        code, detail, status = refusal
        raise CommunityError(code, detail, status)
