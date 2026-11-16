"""Identical minute cadence for beat and the beat-less scheduler."""
NAME = "presence-expiry"
TASK = "apps.presence.tasks.expire_presence_sessions_task"
SCHEDULED_ENTRY = (NAME, TASK, 1)


def beat_entries(tombstones):
    return {} if "presence" in tombstones else {NAME: {"task": TASK, "schedule": 60.0}}
