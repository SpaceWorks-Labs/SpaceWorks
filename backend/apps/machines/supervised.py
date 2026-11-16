"""Supervised machine sessions at workshops (decision 223 (d), P2).

A certified instructor (a staff operator of the machine, or a member holding the machine's
certification) opens a session on one machine, optionally for an event, and adds
supervisees. A supervisee may use the machine only while the session is open
(`may_use_supervised`, the predicate guest "supervised" machine mode calls); each use is a
`SupervisedUse` recorded under the instructor. The machine is exclusive: a supervised
session refuses to open over a live member session, and a member session refuses to start
while one is open (`sessions_rules._machine` calls `open_session_for`).

It reuses the maintenance lockout and the machine's down/under-maintenance state, so a
locked-out machine cannot be supervised either. Inert while `machines.supervised_sessions`
is off.
"""

from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.translation import gettext
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.accounts.account_kind_guards import require_member_account
from apps.audit.services import record
from apps.makerspaces.guards import feature_off, require_module
from apps.makerspaces.platform import feature_enabled

from . import access
from .induction import holds_certification
from .lockout import require_not_locked_out
from .models import MachineSession, SupervisedParticipant, SupervisedSession, SupervisedUse
from .sessions_rules import DOWN, SessionRefused

FEATURE = "machines.supervised_sessions"


def supervised_on(makerspace):
    return feature_enabled(makerspace, FEATURE)


def require_supervised(makerspace):
    require_module(makerspace, "machines")
    if not supervised_on(makerspace):
        raise feature_off(FEATURE)
    return makerspace


def may_instruct(actor, machine):
    """Staff operator of this machine, or an active member certified on its type."""
    if actor is None or not getattr(actor, "is_authenticated", False):
        return False
    return bool(access.can_operate_machine(actor, machine)
                or holds_certification(actor, machine.machine_type, machine.makerspace, include_guest=False))


def open_session_for(machine):
    """The open supervised session on this machine, or None (feeds the member-session gate)."""
    if not supervised_on(machine.makerspace):
        return None
    return SupervisedSession.objects.filter(machine=machine, closed_at__isnull=True).first()


def may_use_supervised(user, machine, at=None):
    """True while `user` is an active supervisee of an open session on `machine` at `at`."""
    if user is None or machine is None or not getattr(user, "pk", None) or not supervised_on(machine.makerspace):
        return False
    moment = at or timezone.now()
    return SupervisedParticipant.objects.filter(
        session__machine=machine, user=user, session__opened_at__lte=moment, added_at__lte=moment,
    ).exclude(removed_at__lte=moment).exclude(session__closed_at__lte=moment).exists()


def _locked(session):
    return SupervisedSession.objects.select_for_update(of=("self",)).select_related(
        "makerspace", "machine__machine_type", "instructor").get(pk=session.pk)


def _lead(actor, session):
    if actor is None or (actor.pk != session.instructor_id and not access.can_manage_machine(actor, session.machine)):
        raise PermissionDenied()


def _open(session):
    if session.closed_at is not None:
        raise SessionRefused("supervised_session_closed", gettext("This supervised session has closed."))


def _require_machine_usable(machine):
    """Down, under maintenance or locked out blocks THIS machine for supervised use, at open AND on
    every use, so a session opened earlier stops recording uses once the machine goes down (audit 0.12.0)."""
    if not machine.is_active or machine.status in DOWN:
        raise SessionRefused("machine_unavailable", gettext("This machine is down or under maintenance."))
    require_not_locked_out(machine)


def _meta(session, **extra):
    return {"supervised_session_id": session.pk, "machine_id": session.machine_id,
            "machine_type_id": session.machine.machine_type_id, **extra}


def _may_bind_event(instructor, machine, event):
    from apps.events import event_authority, event_permissions
    from .models import EventInductionLink
    return event_authority.can(instructor, event, event_permissions.VIEW) or EventInductionLink.objects.filter(
        event=event, certification_type__machine_type_id=machine.machine_type_id).exists()


def _require_adult_instructor(instructor, makerspace):
    """Decision 230 (d): a minor can never instruct, whatever their certification (the minors rule only
    decides whether they may USE a machine; supervising others is adults-only)."""
    from apps.makerspaces.community_policy import minors_on, policy_for
    from apps.makerspaces.minors import is_minor, profile_for
    if minors_on(makerspace) and is_minor(profile_for(makerspace, instructor), policy_for(makerspace)):
        raise SessionRefused("instructor_must_be_adult", gettext("A minor cannot open a supervised session."),
                             status_code=403)


@transaction.atomic
def open_session(machine, instructor, *, event=None, note=""):
    require_supervised(machine.makerspace)
    if not may_instruct(instructor, machine):
        raise PermissionDenied(gettext("Only a certified instructor can open a supervised session."))
    _require_adult_instructor(instructor, machine.makerspace)
    if event is not None and event.makerspace_id != machine.makerspace_id:
        raise ValidationError({"event_id": gettext("Choose an event of this makerspace.")})
    if event is not None and not _may_bind_event(instructor, machine, event):
        # The session's people picker searches the bound event's registrants: bind only an
        # event the instructor works on, or an induction event for this machine's type.
        raise ValidationError({"event_id": gettext("Choose an event you run or an induction for this machine.")})
    _require_machine_usable(machine)
    from .models import MachineServiceRequest
    running_job = MachineServiceRequest.objects.filter(
        assigned_machine_id=machine.pk, status=MachineServiceRequest.Status.IN_PROGRESS).exists()
    if running_job or MachineSession.objects.filter(machine=machine, ended_at__isnull=True).exists():
        raise SessionRefused("machine_in_use", gettext("Someone is using this machine right now."))
    try:
        with transaction.atomic():
            session = SupervisedSession.objects.create(
                makerspace=machine.makerspace, machine=machine, instructor=instructor, event=event,
                note=note[:300], opened_at=timezone.now())
    except IntegrityError:
        raise SessionRefused("machine_in_use", gettext("A supervised session is already open on this machine."))
    record(instructor, "machine_session.supervised_opened", makerspace=session.makerspace, target=session,
           meta=_meta(session, event_id=event.pk if event else None))
    return session


@transaction.atomic
def add_supervisee(session, user, *, actor):
    session = _locked(session)
    require_supervised(session.makerspace)
    _lead(actor, session)
    _open(session)
    if user.pk == session.instructor_id:
        raise ValidationError({"user_id": gettext("The instructor cannot supervise themselves.")})
    require_member_account(user)
    if not user.is_active or user.access_status != "active":
        raise ValidationError({"user_id": gettext("This account is unavailable.")})
    now = timezone.now()
    _require_supervisee_rules(user, session.makerspace, now)
    row, created = SupervisedParticipant.objects.get_or_create(
        session=session, user=user, defaults={"added_by": actor, "added_at": now})
    if not created and row.removed_at is not None:
        row.removed_at, row.added_at, row.added_by = None, now, actor
        row.save(update_fields=["removed_at", "added_at", "added_by"])
    elif not created:
        return row
    record(actor, "machine_session.supervisee_added", makerspace=session.makerspace, target=session,
           meta=_meta(session, user_id=user.pk))
    return row


def _require_supervisee_rules(user, makerspace, now):
    """Audit M8 (decisions 223(d)/(k)): a supervisee is a member here or a guest whose pass allows machines
    under supervision, and a minor must clear the minors rule for machine use, on add AND on every use."""
    from apps.makerspaces.guest_pass_queries import active_pass_for, pass_entitlements
    from apps.makerspaces.minors_guard import require_minor_clearance
    from apps.makerspaces.models import MakerspaceMembership
    if not MakerspaceMembership.objects.filter(makerspace=makerspace, user=user, status="active").exists():
        guest_pass = active_pass_for(user, makerspace, now)
        if guest_pass is None or pass_entitlements(guest_pass).machines not in ("supervised", "after_induction_cert"):
            raise SessionRefused(
                "guest_pass_machines_not_allowed",
                gettext("This person is not a member and their guest pass does not allow supervised machine use."),
                status_code=403)
    require_minor_clearance(user, makerspace, "machine")


def _end_uses(session, user=None, *, now):
    uses = SupervisedUse.objects.filter(session=session, ended_at__isnull=True)
    return uses.filter(user=user).update(ended_at=now) if user else uses.update(ended_at=now)


@transaction.atomic
def remove_supervisee(session, user, *, actor):
    session = _locked(session)
    require_supervised(session.makerspace)
    _lead(actor, session)
    now = timezone.now()
    row = SupervisedParticipant.objects.filter(session=session, user=user, removed_at__isnull=True).first()
    if row is None:
        raise ValidationError({"user_id": gettext("This person is not supervised in this session.")})
    row.removed_at = now
    row.save(update_fields=["removed_at"])
    _end_uses(session, user, now=now)
    record(actor, "machine_session.supervisee_removed", makerspace=session.makerspace, target=session,
           meta=_meta(session, user_id=user.pk))
    return row


@transaction.atomic
def start_use(session, user, *, actor, note=""):
    """Record one use of the machine by a supervisee, under the instructor (the actor leads)."""
    session = _locked(session)
    require_supervised(session.makerspace)
    _lead(actor, session)
    _open(session)
    if not SupervisedParticipant.objects.filter(session=session, user=user, removed_at__isnull=True).exists():
        raise SessionRefused("not_supervised", gettext("Add this person to the session first."), status_code=403)
    _require_supervisee_rules(user, session.makerspace, timezone.now())
    _require_machine_usable(session.machine)
    if SupervisedUse.objects.filter(session=session, user=user, ended_at__isnull=True).exists():
        raise SessionRefused("use_already_open", gettext("This person already has a use in progress."))
    use = SupervisedUse.objects.create(
        session=session, user=user, instructor=session.instructor, started_at=timezone.now(), note=note[:300])
    record(actor, "machine_session.supervised_use_started", makerspace=session.makerspace, target=use,
           meta=_meta(session, use_id=use.pk, user_id=user.pk))
    return use


@transaction.atomic
def end_use(use, *, actor):
    use = SupervisedUse.objects.select_for_update(of=("self",)).select_related(
        "session__machine__machine_type", "session__makerspace").get(pk=use.pk)
    session = use.session
    require_supervised(session.makerspace)
    _lead(actor, session)
    if use.ended_at is not None:
        raise SessionRefused("use_closed", gettext("This use has already ended."))
    use.ended_at = max(timezone.now(), use.started_at)
    use.save(update_fields=["ended_at"])
    record(actor, "machine_session.supervised_use_ended", makerspace=session.makerspace, target=use,
           meta=_meta(session, use_id=use.pk, user_id=use.user_id))
    return use


@transaction.atomic
def close_session(session, *, actor):
    session = _locked(session)
    require_supervised(session.makerspace)
    _lead(actor, session)
    _open(session)
    now = timezone.now()
    _end_uses(session, now=now)
    session.closed_at, session.closed_by = max(now, session.opened_at), actor
    session.save(update_fields=["closed_at", "closed_by"])
    record(actor, "machine_session.supervised_closed", makerspace=session.makerspace, target=session,
           meta=_meta(session, uses=session.uses.count()))
    return session
