"""Release 2 L8: source-gate declaration for the per-space key jobs."""

FANOUT = {
    "apps.encryption.rekey_tasks.advance": "One key job chunk of one space, inside its skip-and-count tenant boundary.",
}


def gate_tasks(internal, fanout):
    internal.update({
        "apps.encryption.rekey_tasks.advance_key_jobs_task": (
            "Each re-encrypt or re-index chunk runs inside its own skip-and-count tenant boundary."
        ),
    })
    fanout.update(FANOUT)
