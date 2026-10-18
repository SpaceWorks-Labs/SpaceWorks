"""Recoverable host initialization, under the existing supervisor operation lock."""

import base64
from pathlib import Path
import tempfile

from .errors import SetupError
from .private_files import check_private, no_links, read_json, write_json


def commit_host_environment(*, ops, static_env, compose, renderer):
    from apps.backup.cloud_environment import init_from_current_environment
    from apps.backup.host_private_file import write_private_file_fsynced, unlink_private_file_fsynced

    ops, static_env = Path(ops), Path(static_env)
    journal = ops / "cloud-initialization-transaction.json"
    targets = (static_env, ops / "database-pointer.env", ops / "compose-topology.json")
    for target in targets:
        no_links(target)
        if target.exists():
            check_private(target)
    if journal.exists():
        transaction = read_json(journal)
        if transaction.get("version") != 1 or transaction.get("paths") != [str(p.absolute()) for p in targets]:
            raise SetupError("host_journal_mismatch", "Recover the matching host initialization journal before retrying.")
        if transaction["state"] == "pending":
            _restore(targets, transaction["previous"], write_private_file_fsynced, unlink_private_file_fsynced)
            transaction["state"] = "rolled_back"
            write_json(journal, transaction)
    # Stage and reproduce Compose before writing any authority target.
    with tempfile.TemporaryDirectory(prefix="cloud-stage-", dir=ops) as temporary:
        stage = Path(temporary)
        result = init_from_current_environment(
            compose_path=compose, static_env_path=stage / "cloud.env",
            pointer_path=stage / "database-pointer.env", topology_record_path=stage / "compose-topology.json",
            compose_renderer=renderer,
        )
        payloads = [p.read_bytes() for p in (stage / "cloud.env", stage / "database-pointer.env", stage / "compose-topology.json")]
        previous = [base64.b64encode(p.read_bytes()).decode("ascii") if p.exists() else None for p in targets]
        if any(old is not None and base64.b64decode(old) != new for old, new in zip(previous, payloads)):
            raise SetupError("host_already_initialized", "Existing host configuration differs. Use supervised settings/update; initialization never resets an active pointer.")
        transaction = {"version": 1, "state": "pending", "paths": [str(p.absolute()) for p in targets], "previous": previous}
        write_json(journal, transaction)
        try:
            for target, payload in zip(targets, payloads):
                write_private_file_fsynced(target, payload)
            transaction["state"] = "done"
            write_json(journal, transaction)
        except BaseException:
            _restore(targets, previous, write_private_file_fsynced, unlink_private_file_fsynced)
            transaction["state"] = "rolled_back"
            write_json(journal, transaction)
            raise
    return result


def _restore(targets, previous, write, unlink):
    for path, encoded in zip(targets, previous):
        if encoded is None:
            if path.exists():
                unlink(path)
        else:
            write(path, base64.b64decode(encoded, validate=True))
