"""Release-2 L10 integration routes: signed printer routes, module checks left to the view.

The registry's module tuple is empty on purpose: the view answers 404 for the whole
`machines.integrations` capability chain (devices, machines, machine_service and the
switch), so a space with the integration off reveals nothing, not even a 400.
"""


def integration_routes(route, signed_mode):
    kinds = frozenset({"printer"})
    return {
        ("devices:device-integration-queue", "GET"): route(signed_mode, "integrations.queue", kinds, ()),
        ("devices:device-integration-job-report", "POST"): route(signed_mode, "integrations.report", kinds, ()),
    }
