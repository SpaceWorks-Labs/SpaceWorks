"""Origin-scope table for release 2 L10's machine-integration binding detail route.

The list and status routes carry `makerspace_id` in the URL; the detail route names only the
binding, so its target is the binding's own space -- a verified custom staff origin then pins
it like every other admin route.
"""

MODEL_LOOKUPS = {
    "admin-machine-type-integration-detail": ("devices.MachineTypeIntegration", "makerspace_id"),
}
