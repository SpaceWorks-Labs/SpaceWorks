"""NCA audit 0.12.0: a scheduled task must be sent under the name Celery registered it as.

Celery names a ``shared_task`` after the module that DEFINES it, not one that re-exports it, so a
beat entry naming a re-export (``apps.backup.tasks.push_offsite_backups_task`` for a task defined
in ``tasks_offsite``) is an unregistered task at run time while ``getattr`` still resolves it.
The managed DatabaseScheduler dispatches only cloud-catalogue rows, so every beat entry must be
in the catalogue too, or it silently never runs on a managed deployment.
"""
import importlib

from django.conf import settings

from apps.operations.cloud_jobs.catalog import all_declarations


def _registered_name(path):
    module, _, attribute = path.rpartition(".")
    # A plain callable (not a Celery task) is invoked by path, so its path is its name.
    return getattr(getattr(importlib.import_module(module), attribute), "name", path)


def test_every_beat_entry_names_the_registered_task():
    wrong = {key: (entry["task"], _registered_name(entry["task"]))
             for key, entry in settings.CELERY_BEAT_SCHEDULE.items()
             if _registered_name(entry["task"]) != entry["task"]}
    assert not wrong, wrong


def test_every_catalogue_row_names_the_registered_task():
    wrong = {task.key: task.path for task in all_declarations() if _registered_name(task.path) != task.path}
    assert not wrong, wrong


def test_every_beat_entry_is_in_the_cloud_catalogue():
    catalogue = {task.path for task in all_declarations()}
    missing = sorted(entry["task"] for entry in settings.CELERY_BEAT_SCHEDULE.values()
                     if entry["task"] not in catalogue)
    assert not missing, f"add these to LEGACY_ENTRIES in apps/operations/cloud_jobs/catalog.py: {missing}"
