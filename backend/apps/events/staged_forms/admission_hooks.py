"""Admission invokes the same stage owner services as ordinary registration."""
from .registration_hooks import activate_for_participant_locked
from .guards import require_complete_locked, readiness
from .trigger_service import resolve_participant


def require_action_locked(*, event, member_id, action):
    return require_complete_locked(resolve_participant(event=event, owner_id=member_id), action)


def check_in_readiness(*, event, member_id):
    return readiness(resolve_participant(event=event, owner_id=member_id), "check_in")
