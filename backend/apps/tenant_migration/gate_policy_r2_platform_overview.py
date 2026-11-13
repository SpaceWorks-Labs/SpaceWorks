"""Release 2 #183A: source-gate declaration for the superadmin platform-overview computation."""


def gate_tasks(exemptions):
    exemptions.update({
        "apps.operations.tasks_platform_overview.compute_platform_overview_task": (
            "Read-only platform monitoring across spaces (counts and per-currency money); writes "
            "only a disposable deployment cache entry, never tenant rows."
        ),
    })
