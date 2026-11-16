from ..capability import Capability

# No new payload: the server stores the `telemetry` block of status reports and `sensor.reading` events as time series
# (raw -> 1-minute -> 15-minute rollups). A capability declaration lets staff switch it per binding.
CAPABILITY = Capability(
    "telemetry.history", "Server-side time series of temperatures, metrics and sensor readings with downsampling.",
    targets=("machine", "door", "space", "storage_location"), routes=("GET admin/adapter-bindings/{id}/telemetry",),
    switch="machines.integrations.telemetry_history",
)
