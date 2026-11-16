from ..capability import Capability

CAPABILITY = Capability(
    "file.fetch", "Fetch the job artifact through a short-lived signed URL.", targets=("machine",),
    routes=("GET jobs/{id}/file",),
)
