"""Lane r2-parity-followups (#190): source-gate declarations.

Re-encrypting or purging one space's archive on a retired backup key, queued from the web
console, runs under that space's own tenant boundary: the task resolves its space from the
archive, so a frozen space refuses the job like any other tenant write.
"""


def gate_tasks(resolvers):
    resolvers["apps.backup.tasks_space_keys.space_archive_key_task"] = ("backup.BackupArchive", 0, "makerspace_id")
