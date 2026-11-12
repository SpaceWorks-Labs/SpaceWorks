"""Release-2 lane L10: machine-integration foundations (#76, #158).

Decisions 310-312 extend this: `machines.integrations` is now frontend-exposed (Settings > Features) and the
Device Adapter API v1 hangs off it, with child switches `.access`, `.usage_billing` and `.video` (all off by
default). The text below describes the original foundation.

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
            frontend_exposed=True, app_label="devices",
        ),
        # Decision 312: child switches of the Device Adapter API (each needs the parent; all off by default).
        feature(
            "machines.integrations.access", "machines", "Adapter access control",
            "Lets a device adapter decide who may use a machine or open a door: card, NFC or PIN in, "
            "allow or deny out, through the existing session rules.",
            requires_modules=("devices", "machine_service"), requires_features=("machines.integrations",),
            frontend_exposed=True, app_label="devices",
        ),
        feature(
            "machines.integrations.usage_billing", "machines", "Adapter usage logging",
            "Lets a device adapter record what a machine measured (active and idle minutes, outcome) "
            "as immutable usage records.",
            requires_modules=("devices", "machine_service"), requires_features=("machines.integrations",),
            frontend_exposed=True, app_label="devices",
        ),
        feature(
            "machines.integrations.video", "machines", "Adapter camera watch",
            "Lets staff open a short, audited camera watch on a machine through its device adapter. "
            "Nothing is recorded unless recording is on.",
            requires_modules=("devices", "machine_service"), requires_features=("machines.integrations",),
            frontend_exposed=True, app_label="devices",
        ),
        feature(
            "machines.integrations.kiosk", "machines", "Adapter kiosk checkout",
            "Lets a kiosk device sign a member in (card, NFC or PIN) and run self-checkout and return through "
            "the normal self-checkout rules: photo evidence, eligible tools and audit are still required.",
            requires_modules=("devices", "machine_service"), requires_features=("machines.integrations",),
            frontend_exposed=True, app_label="devices",
        ),
        feature(
            "machines.integrations.recording", "machines", "Adapter camera recording",
            "Lets a camera watch be recorded when staff ask for it. Recordings are deleted after a week and "
            "every one is audited.",
            requires_modules=("devices", "machine_service"), requires_features=("machines.integrations.video",),
            frontend_exposed=True, app_label="devices",
        ),
    )
