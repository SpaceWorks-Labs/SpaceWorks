"""Release 2 L3: source-gate declarations for the card-engine sweeps."""


def gate_tasks(internal, exemptions, resolvers):
    resolvers.update({
        # One bounded chunk of one card job; the job row names its space.
        "apps.card_designs.tasks.process_card_job": ("card_designs.CardJob", 0, "makerspace_id"),
    })
    exemptions.update({
        "apps.card_designs.tasks.fetch_card_font_task": (
            "Platform font library: fetches one font family into the shared CardFont rows (OMITTED); "
            "no tenant row is read or written."
        ),
    })
    internal.update({
        "apps.card_designs.tasks.resume_card_jobs": (
            "Each card-job chunk reads and writes inside its job's own space; a frozen space's job waits."
        ),
        "apps.card_designs.tasks.purge_expired_card_job_results": (
            "Deletes only expired temporary result objects of each job's own space."
        ),
        "apps.card_designs.tasks.refresh_wallet_passes": (
            "Each pass refresh reads its own card's space and calls the wallet provider; no tenant write crosses spaces."
        ),
        "apps.events.tasks_id_cards.reconcile_event_id_cards_task": (
            "Each event's card issue and revoke runs in that event's own space."
        ),
        "apps.card_designs.tasks.remind_photo_requests": (
            "Each reminder stamps one request in its own space and queues one notice."
        ),
    })
