"""Release-2 lane L12: machines and loans depth (#76, #94, #140-#142).

Every switch keeps its data when turned off (#95, #128 C-8). Work orders, the downtime
ledger, meter-based maintenance and lockout ride the L17 `machines.maintenance` switch,
and the To-Buy rows ride `machines.tobuy` / `inventory.tobuy`; none of them gets a key here.

Two keys are ON by default because they ARE today's behaviour, now uniform (#140/#142):

* `machines.job_requests` -- the one "Request a job" flow for every machine type that
  accepts jobs (the 3D-printer form included). Off: no member submits a job; staff keep
  every job already in the queue.
* `machines.job_quotes` -- staff send a quote the member approves before the job queues,
  per machine type (off / above an amount / always; #142 OQ-2 defaults to "always" when
  the type is priced). Off: no type asks for a quote.

Everything else is new behaviour and starts off.
"""


def definitions(feature):
    return (
        feature(
            "inventory.consumables", None, "Consumables",
            "Mark take-and-go items (screws, glue) as consumables: they are logged as used, never "
            "lent, and one staff list shows them beside machine consumables and material pools.",
        ),
        feature(
            "inventory.vendors", None, "Vendors",
            "Saved suppliers for To-Buy purchases and warranties.",
        ),
        feature(
            "inventory.expected_back", "public_inventory", "Expected-back dates",
            "Items that opt in show the earliest date a borrowed-out unit is due back. Never who "
            "holds it or how many are out.",
        ),
        feature(
            "loans.reservations", "request_workflow", "Loan reservations",
            "Members choose when they will collect, up to a set number of days ahead.",
        ),
        feature(
            "loans.pickup_windows", "request_workflow", "Pickup windows",
            "An accepted request that is not collected in time expires and its items are free again.",
        ),
        feature(
            "loans.waitlist", "request_workflow", "Loan waitlist",
            "Members queue for an item that is out; when one comes back it is held for the first "
            "in line for a set time.",
            requires_modules=("notifications",),
        ),
        feature(
            "loans.withdrawals", "request_workflow", "Withdraw requests",
            "Members withdraw their own request before it is handed over.",
        ),
        feature(
            "machines.job_requests", "machine_service", "Machine job requests",
            "One request form for every machine type that accepts jobs: files, material and notes, "
            "a live queue position and ETA, pickup codes, and the full job timeline.",
            default_enabled=True, requires_modules=("machines",),
        ),
        feature(
            "machines.job_quotes", "machine_service", "Job quotes",
            "Staff send a quote that the member approves before the job joins the queue.",
            default_enabled=True, requires_features=("machines.job_requests",),
        ),
        feature(
            "machines.batch_start", "machine_service", "Batch start",
            "Start several queued jobs together on one machine run; time and material are split "
            "across the batch.",
            requires_features=("machines.job_requests",),
        ),
        feature(
            "machines.pay_before_pickup", "machine_service", "Pay before pickup",
            "A finished job is handed over only once its charge is settled.",
            requires_features=("machines.job_requests",),
        ),
        feature(
            "machines.time_booking", "machines", "Machine time booking",
            "Book a machine for a time slot through bookings; machine types that require a booking "
            "can then only be used by the person holding it.",
            requires_modules=("bookings",),
        ),
    )
