"""Native member machine targets (decision 545); ownership is still checked by views.

Object routes resolve the row's tenant even while its module is off. Lists require
an explicit makerspace query when a native selection is supplied, just like staff
query-scoped lists. Neither table grants membership, staff authority or ownership.
"""

MODEL_LOOKUPS = {
    **{name: ("machines.MachineServiceRequest", "makerspace_id") for name in (
        "member-machine-job-detail", "member-machine-job-approve-quote",
        "member-machine-job-decline-quote", "member-machine-job-resubmit",
        "member-machine-job-consumables",
    )},
    "member-machine-session-stop": ("machines.MachineSession", "makerspace_id"),
    **{name: ("machines.SupervisedSession", "makerspace_id") for name in (
        "member-supervised-session", "member-supervised-supervisees",
        "member-supervised-people", "member-supervised-supervisee-remove",
        "member-supervised-use-start", "member-supervised-session-close",
    )},
    "member-supervised-use-end": ("machines.SupervisedUse", "session__makerspace_id"),
    "member-machine-type-document-url": ("machines.MachineTypeDocument", "makerspace_id"),
}
# Existing paths carry machine_id. Keep MODEL_LOOKUPS' pk convention intact
# and adapt these exact routes without renaming shipped URL kwargs.
MACHINE_ID_ROUTES = frozenset({
    "member-machine-session-preview", "member-machine-session-start",
    "member-supervised-session-open",
})
QUERY_MAKERSPACE_PARAMS = {"member-machine-jobs": "makerspace", "member-machine-sessions": "makerspace"}
QUERY_SCOPED_ROUTES = set(QUERY_MAKERSPACE_PARAMS)


def member_machine_route_targets(name, kwargs):
    if name not in MACHINE_ID_ROUTES:
        return None
    from django.apps import apps
    target = apps.get_model("machines.Machine").objects.filter(
        pk=kwargs.get("machine_id"),
    ).values_list("makerspace_id", flat=True).first()
    return name, {target} if target is not None else set(), target is None, True
