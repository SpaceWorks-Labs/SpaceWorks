"""Release 2 L18: source-gate declarations for the pledge and sponsor-perk sweeps."""


def gate_tasks(internal):
    internal.update({
        "apps.payments.donations.tasks.raise_pledges_task": (
            "Each due pledge raises its gift and charge inside its own space's tenant write boundary, "
            "which holds that space's source gate."
        ),
        "apps.payments.donations.tasks.remind_perks_task": (
            "Each perk reminder stamps one perk and queues one staff notice inside its own space's boundary."
        ),
    })
