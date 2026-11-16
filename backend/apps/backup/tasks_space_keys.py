"""#190 follow-up: re-encrypt or purge one space's archive on a retired key, queued from the console."""

from celery import shared_task


@shared_task(bind=True, max_retries=0)
def space_archive_key_task(self, archive_id, action, actor_id):
    # The space's source gate applies: gate_policy resolves the archive's space and runs
    # this under its tenant boundary, so a frozen space refuses the job.
    from apps.backup.space_archive_keys import run
    return run(archive_id, action, actor_id)
