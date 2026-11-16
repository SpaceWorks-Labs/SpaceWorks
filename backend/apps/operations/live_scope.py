"""Per-reader redaction of live-update hints (owner requirement: each role sees its own area).

The makerspace channel carries one hint per audit row of the space. Every subscriber
still receives every hint's ``kind`` and ``target_type`` (the console invalidates its
cached queries by kind, so a member's own request refreshes when staff accept it), but
WHO acted (``actor_id``) and WHICH object (``target_id``) travel only to a reader whose
areas include the action's audit area (``apps.audit.areas``), to the actor themself,
to the Space Manager and to the superadmin. A plain member, a Shop Manager or a
Technician no longer learns which payment was refunded or which member was revoked.
"""

import json

from apps.accounts import rbac
from apps.audit import areas

from . import live

_SPACE_PREFIX = live.makerspace_channel(0)[:-1]


def stream_areas(actor, makerspace_id):
    actions = rbac.effective_actions(actor, makerspace_id)
    held = areas.areas_for_actions(actions)
    if rbac.Action.VIEW_INVENTORY in actions:
        held |= {areas.LENDING}
    # Machines audit 0.12.0: a hint names no machine type, so a type-scoped Machine Manager keeps
    # only `kind`/`target_type` for machine and repair hints (the audit log narrows them per
    # type), and a coverage-scoped Technician gets no repair ids. Cache invalidation is by kind.
    from apps.machines import role_scope
    narrowed = rbac.Action.MANAGE_MACHINES in actions and role_scope.manage_scope_for(
        actor, makerspace_id) is not role_scope.EXEMPT
    if narrowed:
        held.discard(areas.MACHINES)
    elif set(areas.REPAIR_SUBJECT_ACTIONS.values()) & set(actions):
        held |= {areas.REPAIRS}
    return held


def redactor_for(actor):
    """A ``(channel, data) -> data`` filter for one stream; ``None`` for the superadmin."""
    if rbac._is_superadmin(actor):
        return None
    held_by_space = {}

    def redact(channel, data):
        if not channel.startswith(_SPACE_PREFIX):
            return data
        try:
            space_id = int(channel[len(_SPACE_PREFIX):])
            payload = json.loads(data)
        except (TypeError, ValueError):
            return data
        if not isinstance(payload, dict) or payload.get("actor_id") == actor.pk:
            return data
        if space_id not in held_by_space:
            held_by_space[space_id] = stream_areas(actor, space_id)
        held = held_by_space[space_id]
        if areas.PLATFORM in held or set(areas.areas_for_action(str(payload.get("kind") or ""))) & held:
            return data
        payload.update(actor_id=None, target_id="")
        return json.dumps(payload, separators=(",", ":"))

    return redact
