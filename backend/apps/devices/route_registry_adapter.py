"""Device Adapter API v1 routes. The module tuple is empty on purpose: the views answer 404 for the whole
`machines.integrations` chain (and each capability's child switch), so a space with the switch off reveals nothing."""

ADAPTER = frozenset({"adapter"})
ROUTES = {
    "devices:device-adapter-hello": ("POST", "adapter.hello"),
    "devices:device-adapter-bindings": ("GET", "adapter.bindings"),
    "devices:device-adapter-status": ("POST", "adapter.status"),
    "devices:device-adapter-events": ("POST", "adapter.events"),
    "devices:device-adapter-command-lease": ("POST", "adapter.commands.lease"),
    "devices:device-adapter-command-ack": ("POST", "adapter.commands.ack"),
    "devices:device-adapter-access": ("POST", "adapter.access.authorize"),
    "devices:device-adapter-session-start": ("POST", "adapter.sessions.start"),
    "devices:device-adapter-session-stop": ("POST", "adapter.sessions.stop"),
    "devices:device-adapter-usage": ("POST", "adapter.usage"),
    "devices:device-adapter-job-lease": ("POST", "adapter.jobs.lease"),
    "devices:device-adapter-job-ack": ("POST", "adapter.jobs.ack"),
    "devices:device-adapter-job-progress": ("POST", "adapter.jobs.progress"),
    "devices:device-adapter-job-report": ("POST", "adapter.jobs.report"),
    "devices:device-adapter-job-file": ("GET", "adapter.jobs.file"),
    "devices:device-adapter-kiosk-start": ("POST", "adapter.kiosk.start"),
    "devices:device-adapter-kiosk-end": ("DELETE", "adapter.kiosk.end"),
    "devices:device-adapter-kiosk-scan": ("POST", "adapter.kiosk.scan"),
    "devices:device-adapter-kiosk-evidence": ("POST", "adapter.kiosk.evidence"),
    "devices:device-adapter-kiosk-issue": ("POST", "adapter.kiosk.issue"),
    "devices:device-adapter-kiosk-return": ("POST", "adapter.kiosk.return"),
    "devices:device-adapter-media-snapshot": ("POST", "adapter.media.snapshot"),
    "devices:device-adapter-media-recording": ("POST", "adapter.media.recording"),
    "devices:device-adapter-artifact-request": ("POST", "adapter.artifacts.request"),
    "devices:device-adapter-artifact-complete": ("POST", "adapter.artifacts.complete"),
    "devices:device-adapter-access-cache": ("GET", "adapter.access.cache"),
    "devices:device-adapter-offline-decisions": ("POST", "adapter.access.offline_decisions"),
    "devices:device-adapter-config": ("GET", "adapter.config.read"),
    "devices:device-adapter-config-ack": ("POST", "adapter.config.ack"),
    "devices:device-adapter-time": ("GET", "adapter.time"),
}
# One route name, two methods.
EXTRA = {("devices:device-adapter-media-signal", "GET"): "adapter.media.signal.read",
         ("devices:device-adapter-media-signal", "POST"): "adapter.media.signal.write"}


def adapter_routes(route, signed_mode):
    table = {(name, method): route(signed_mode, action, ADAPTER, ()) for name, (method, action) in ROUTES.items()}
    table.update({key: route(signed_mode, action, ADAPTER, ()) for key, action in EXTRA.items()})
    return table
