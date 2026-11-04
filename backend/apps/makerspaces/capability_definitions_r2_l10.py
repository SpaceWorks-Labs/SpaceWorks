"""Release-2 lane L10: machine-integration foundations (#76, #158).

One switch, `machines.integrations`, off by default. It gates only the server-side
foundation a future printer agent would use: per-type integration bindings, the status
snapshot carried on the signed heartbeat, the job queue pull and the job reports. The
integration itself (agent, vendor adapter, fleet scheduling, live controls, camera, shelf
pointer) is DEFERRED (#76), so no console screen exists and the switch stays out of the
frontend (`frontend_exposed=False`): it is reachable in /control/ only. With it off every
integration route answers 404 and nothing is scheduled. It needs the `devices` module (the
signed device identity) and `machine_service` (the workflow job reports map onto).
"""


def definitions(feature):
    return (
        feature(
            "machines.integrations", "machines", "Machine integrations (foundation)",
            "Foundation only; the integration is deferred (#76). Lets an enrolled printer device "
            "bound to a machine type pull its approved jobs, report start, completion or failure "
            "through the machine-service workflow, and send a bounded status snapshot.",
            requires_modules=("devices", "machine_service"),
            frontend_exposed=False, app_label="devices",
        ),
    )
