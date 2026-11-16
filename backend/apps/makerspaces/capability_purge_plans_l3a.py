"""Capability purge plans for release 0.12.0 lane L3a (decision 223): superadmin-only, previewed, audited.

* `machines.induction_events` -- event induction links and guest certifications. Member
  certification grants stay (they are the member's training record).
* `machines.supervised_sessions` -- supervised sessions with their supervisees and uses.
* `safety.incidents` -- incidents and their follow-up actions. Repairs, loans and events
  the incidents pointed at stay.
"""


def _induction_delete(space, cursor):
    from apps.machines.models import EventInductionLink, GuestCertificationGrant
    from .module_purge_collectors_single_model import _counts, _delete
    links, link_labels = _delete(EventInductionLink.objects.filter(makerspace=space))
    guests, guest_labels = _delete(GuestCertificationGrant.objects.filter(makerspace=space))
    return _counts(model_labels=link_labels | guest_labels, induction_links=links, guest_certifications=guests)


def _induction_preview(space):
    from apps.machines.models import EventInductionLink, GuestCertificationGrant
    return {"induction_links": EventInductionLink.objects.filter(makerspace=space).count(),
            "guest_certifications": GuestCertificationGrant.objects.filter(makerspace=space).count()}


def _supervised_delete(space, cursor):
    from apps.machines.models import SupervisedSession
    from .module_purge_collectors_single_model import _counts, _delete
    sessions, labels = _delete(SupervisedSession.objects.filter(makerspace=space))
    return _counts(model_labels=labels, supervised_sessions=sessions)


def _supervised_preview(space):
    from apps.machines.models import SupervisedParticipant, SupervisedSession, SupervisedUse
    return {"supervised_sessions": SupervisedSession.objects.filter(makerspace=space).count(),
            "supervisees": SupervisedParticipant.objects.filter(session__makerspace=space).count(),
            "uses": SupervisedUse.objects.filter(session__makerspace=space).count()}


def _incident_delete(space, cursor):
    from apps.maintenance.models import Incident
    from .module_purge_collectors_single_model import _counts, _delete
    incidents, labels = _delete(Incident.objects.filter(makerspace=space))
    return _counts(model_labels=labels, incidents=incidents)


def _incident_preview(space):
    from apps.maintenance.models import Incident, IncidentAction
    return {"incidents": Incident.objects.filter(makerspace=space).count(),
            "actions": IncidentAction.objects.filter(incident__makerspace=space).count()}


def plans(plan):
    return (
        plan("machines.induction_events", "Event induction links and guest certifications. Member certification "
             "grants stay.", _induction_delete, _induction_preview),
        plan("machines.supervised_sessions", "Supervised workshop sessions, their supervisees and recorded uses.",
             _supervised_delete, _supervised_preview),
        plan("safety.incidents", "Incidents and near misses with their follow-up actions. Linked repairs, loans "
             "and events stay.", _incident_delete, _incident_preview),
    )
