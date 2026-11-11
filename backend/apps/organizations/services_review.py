"""Organization review workflow (O-B5): pending organizations are inert until approved.

Only a superadmin decides (with recent re-authentication at the view). A declined
organization keeps its slug for 30 days on the declined row itself, then the slug is
released lazily the next time someone tries to create it. A suspended organization stays
active, so its members keep their data rights, but it has no public face and takes no new
links or invitations. Every transition is locked, appended to `OrganizationReview` and
audited.
"""
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.audit import services as audit
from apps.organizations import governance, notifications_review
from apps.organizations.access import is_superadmin
from apps.organizations.models import Organization, OrganizationReview
from apps.organizations.services_console import OrganizationConflict

SLUG_HOLD_DAYS = 30
S = Organization.ReviewStatus
A = OrganizationReview.Action

# (current standing, decision) -> (new standing, review action)
_DECISIONS = {
    (S.PENDING_REVIEW, "approve"): (S.APPROVED, A.APPROVED),
    (S.CHANGES_REQUESTED, "approve"): (S.APPROVED, A.APPROVED),
    (S.PENDING_REVIEW, "decline"): (S.DECLINED, A.DECLINED),
    (S.CHANGES_REQUESTED, "decline"): (S.DECLINED, A.DECLINED),
    (S.PENDING_REVIEW, "request_changes"): (S.CHANGES_REQUESTED, A.CHANGES_REQUESTED),
    (S.APPROVED, "suspend"): (S.SUSPENDED, A.SUSPENDED),
    (S.SUSPENDED, "reactivate"): (S.APPROVED, A.REACTIVATED),
}
DECISIONS = frozenset(decision for _, decision in _DECISIONS)
_REASON_REQUIRED = frozenset({"decline", "request_changes", "suspend"})


def review_required() -> bool:
    return bool(getattr(settings, "ORGANIZATION_REVIEW_REQUIRED", False))


def is_inert(organization) -> bool:
    """True while the organization may not have a public page, links or invitations."""
    return organization.review_status != S.APPROVED


def require_not_inert(organization):
    if is_inert(organization):
        raise OrganizationConflict("This organization is not approved yet.")


def submit_new(organization, actor):
    """Called inside the creating transaction: start the review of a new organization."""
    organization.review_status = S.PENDING_REVIEW
    organization.save(update_fields=["review_status", "updated_at"])
    OrganizationReview.objects.create(organization=organization, action=A.SUBMITTED, actor=actor)
    audit.record(actor, "organization.review_submitted", target=organization)
    notifications_review.notify_submitted(organization)


@transaction.atomic
def resubmit(organization, actor, note=""):
    """The applicant answers a changes request (needs organization profile governance)."""
    locked = Organization.objects.select_for_update().get(pk=organization.pk)
    if governance.MANAGE_ORGANIZATION_PROFILE not in governance.actions_for(actor, locked):
        raise PermissionDenied()
    if locked.review_status != S.CHANGES_REQUESTED:
        raise OrganizationConflict("Only an organization with requested changes can be resubmitted.")
    locked.review_status = S.PENDING_REVIEW
    locked.save(update_fields=["review_status", "updated_at"])
    OrganizationReview.objects.create(
        organization=locked, action=A.SUBMITTED, actor=actor, reason=(note or "")[:2000])
    audit.record(actor, "organization.review_submitted", target=locked, meta={"resubmitted": True})
    notifications_review.notify_submitted(locked)
    return locked


@transaction.atomic
def decide(organization, actor, decision, reason=""):
    if not is_superadmin(actor):
        raise PermissionDenied()
    if decision not in DECISIONS:
        raise ValidationError({"decision": gettext("Unknown decision.")})
    reason = (reason or "").strip()
    if decision in _REASON_REQUIRED and not reason:
        raise ValidationError({"reason": gettext("A reason is required.")})
    if len(reason) > 2000:
        raise ValidationError({"reason": gettext("Use at most 2,000 characters.")})
    locked = Organization.objects.select_for_update().get(pk=organization.pk)
    outcome = _DECISIONS.get((locked.review_status, decision))
    if outcome is None:
        raise OrganizationConflict("This decision does not apply to the organization's current standing.")
    new_status, action = outcome
    locked.review_status = new_status
    fields = ["review_status", "updated_at"]
    if decision == "decline":
        # The declined row keeps the slug for SLUG_HOLD_DAYS; inactive removes it from every list.
        locked.is_active = False
        fields.append("is_active")
    locked.save(update_fields=fields)
    OrganizationReview.objects.create(organization=locked, action=action, actor=actor, reason=reason)
    audit.record(actor, f"organization.review_{action.value}", target=locked,
                 meta={"reason": reason} if reason else None)
    notifications_review.notify_decision(locked, action.value, reason)
    return locked


def assert_slug_available(slug):
    """Refuse a slug held by a declined organization; release it once the hold has lapsed."""
    held = Organization.objects.filter(slug=slug, review_status=S.DECLINED).first()
    if held is None:
        return
    declined = held.reviews.filter(action=A.DECLINED).first()
    until = (declined.created_at if declined else held.updated_at) + timedelta(days=SLUG_HOLD_DAYS)
    if until > timezone.now():
        raise OrganizationConflict("This slug is held for a recently declined organization.")
    if not held.makerspace_links.exists():
        held.delete()
