"""Decision 321: child switches of the Device Adapter API's media and data capabilities (all off by default).

Audio is more sensitive than video, so listening, talking and audio recording are three separate switches.
"""

_PARENT = ("machines.integrations",)
_MODULES = ("devices", "machine_service")

_ROWS = (
    ("audio", "Adapter audio", "Lets staff listen (receive-only) to a device audio track while a camera watch is open."),
    ("talk", "Adapter two-way talk",
     "Lets staff speak to a device (for example a door intercom) with push-to-talk. Every press is audited."),
    ("audio_recording", "Adapter audio recording",
     "Lets a watch's audio be recorded when staff acknowledge the audio notice. Audio is deleted after three days."),
    ("artifacts", "Adapter timelapses and previews",
     "Lets a device upload timelapses, job thumbnails and failure snapshots, kept privately with a retention window."),
    ("detections", "Adapter detection alerts",
     "Lets a device report detections (failure, smoke, fire, person) that notify staff and the job owner."),
    ("telemetry_history", "Adapter telemetry history",
     "Keeps temperatures, power and sensor readings as charts, thinned out over time."),
    ("diagnostics", "Adapter diagnostics", "Shows adapter health and firmware and lets staff request a log bundle."),
    ("offline_cache", "Adapter offline access cache",
     "Lets a door or machine decide access while offline from a short-lived signed list of card digests."),
)


def definitions(feature):
    out = []
    for key, label, description in _ROWS:
        full = f"machines.integrations.{key}"
        requires = _PARENT if key not in ("audio_recording",) else ("machines.integrations.audio",)
        out.append(feature(full, "machines", label, description, requires_modules=_MODULES,
                           requires_features=requires, frontend_exposed=True, app_label="devices"))
    return tuple(out)
