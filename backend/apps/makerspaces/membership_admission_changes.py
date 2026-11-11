"""Parity O-B2: send a join request back for changes, and the applicant's single resubmission.

    requested | awaiting_vouches --request_changes--> changes_requested --resubmit--> requested | awaiting_vouches

* Staff (`manage_members`, inside their unit scope) ask once per request, with a note the applicant reads. The
  expiry clock restarts so the applicant has a fair window. Behind `membership.ask_changes`.
* The applicant (and only the applicant) edits answers and join-form extras and resubmits; the request goes back
  to the queue (or to the vouching step when vouching is on, keeping the vouches already given). There is no second
  round: a request already sent back once cannot be sent back again, which is what bounds the loop.
* A request waiting for changes can still be cancelled by the applicant or declined by staff (both go through
  `close_admission` / `revoke_request`), and it expires like any open request.
* Switching `membership.ask_changes` off never strands such a request: resubmission stays available, only new
  "ask for changes" calls are refused.

Lock order matches the rest of admission: makerspace, then request.
"""
from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.accounts import rbac
from apps.audit import services as audit
from apps.makerspaces import membership_join_fields
from apps.makerspaces.member_unit_scope import require_request_in_scope
from apps.makerspaces.membership_admission_settings import AdmissionError, settings_for, vouching_on
from apps.makerspaces.membership_features import require_membership_feature_locked
from apps.makerspaces.models import Makerspace, MembershipRequest

MAX_ROUNDS = 1
ASKABLE_STATES = ("requested", "awaiting_vouches")


def _locked(request_id, makerspace_id):
    space = Makerspace.objects.select_for_update().get(pk=makerspace_id)
    row = MembershipRequest.objects.select_for_update().select_related("selected_plan", "user").get(
        pk=request_id, makerspace=space)
    return space, row


def request_changes(actor, request, reason):
    from apps.tenant_migration.gate_runtime import assert_write_allowed
    reason = (reason or "").strip()
    if not reason or len(reason) > 1000:
        raise ValidationError({"reason": gettext("Tell the applicant what to change (up to 1000 characters).")})
    with transaction.atomic():
        assert_write_allowed(request.makerspace_id)
        space, row = _locked(request.pk, request.makerspace_id)
        if not rbac.can(actor, rbac.Action.MANAGE_MEMBERS, space.pk):
            raise PermissionDenied()
        require_request_in_scope(actor, row, rbac.Action.MANAGE_MEMBERS)
        require_membership_feature_locked(space.pk, "ask_changes")
        if row.assigned_role_id and row.assigned_role.granted_actions:
            raise AdmissionError("membership_changes_not_for_staff", gettext("Staff invitations cannot be sent back."))
        if not row.admission_managed or row.user_id is None or row.state not in ASKABLE_STATES or row.approved_at:
            raise AdmissionError("membership_changes_not_allowed",
                                 gettext("Only a pending application can be sent back for changes."))
        if row.changes_rounds >= MAX_ROUNDS:
            raise AdmissionError("membership_changes_already_asked",
                                 gettext("This application was already sent back once."))
        previous, now = row.state, timezone.now()
        row.state = MembershipRequest.State.CHANGES_REQUESTED
        row.changes_note, row.changes_requested_at = reason, now
        row.changes_rounds += 1
        row.expires_at = now + timedelta(days=settings_for(space).request_expiry_days)
        row.save(update_fields=["state", "changes_note", "changes_requested_at", "changes_rounds", "expires_at",
                                "updated_at"])
        audit.record(actor, "membership.changes_requested", makerspace=space, target=row,
                     meta={"from_state": previous, "to_state": row.state, "round": row.changes_rounds})
        from apps.makerspaces.membership_admission_notifications import notify_admission
        notify_admission(row, "changes_requested")
    return row


def resubmit(user, request, application_answers=None, join_fields=None):
    """The applicant's edited answers; returns the request back in the queue."""
    from apps.makerspaces.guards import require_module
    from apps.makerspaces.membership_plan_policy import plan_policy
    from apps.tenant_migration.gate_runtime import assert_write_allowed
    with transaction.atomic():
        assert_write_allowed(request.makerspace_id)
        space, row = _locked(request.pk, request.makerspace_id)
        if row.user_id != user.pk:
            raise PermissionDenied()
        require_module(space, "membership")
        if row.state != MembershipRequest.State.CHANGES_REQUESTED:
            raise AdmissionError("membership_resubmit_not_allowed",
                                 gettext("This application is not waiting for changes."))
        if row.expires_at and row.expires_at <= timezone.now():
            raise AdmissionError("membership_request_expired", gettext("This membership application has expired."))
        extras = membership_join_fields.clean(space, row.selected_plan, join_fields,
                                              existing=membership_join_fields.stored(row))
        row.application_answers = membership_join_fields.encode(row.application_schema, application_answers, extras)
        policy = plan_policy(space, row.selected_plan, settings_for(space))
        row.state = (MembershipRequest.State.AWAITING_VOUCHES if vouching_on(space, policy)
                     else MembershipRequest.State.REQUESTED)
        row.save(update_fields=["state", "application_answers", "updated_at"])
        audit.record(user, "membership.request_resubmitted", makerspace=space, target=row,
                     meta={"from_state": "changes_requested", "to_state": row.state, "round": row.changes_rounds})
        from apps.makerspaces.membership_admission_notifications import notify_admission
        notify_admission(row, "resubmitted")
    return row
