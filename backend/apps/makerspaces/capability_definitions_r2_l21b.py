"""Release-2 lane L21b: judging extras, hackathon money, saved views and the gallery search.

Every key is a capability under `events` and keeps its data when turned off (#95, #128 C-8). All
are off by default except the gallery search, which is on wherever the project gallery is on.

* `events.finalists` -- advance finalists between rounds and publish them (X51).
* `events.prize_payouts` -- prize money per winner and hand-recorded payouts in the ledger (C-38).
* `events.entry_fees` -- an entry fee per project; the project stays a draft until paid (X50).
* `events.paid_teams` -- one fixed team price, paid once by the leader after confirming (C-39).
* `events.saved_views` -- saved views and filtered CSV exports on staff event lists (X40).
* `events.gallery_search` -- search, sort and award filters on the public gallery (X54).
"""


def definitions(feature):
    hackathons = ("events.hackathons",)
    return (
        feature("events.finalists", "events", "Finalists",
                "Advance the top projects (or hand-picked ones) from a finished judging round into the next "
                "round, and publish the finalists separately from the results.", requires_features=hackathons),
        feature("events.prize_payouts", "events", "Prize money and payouts",
                "Set a prize amount per winner and record each payout by hand; every payout and reversal is "
                "an expense in the finance ledger. Nothing is ever paid automatically.",
                requires_features=hackathons),
        feature("events.entry_fees", "events", "Project entry fees",
                "Charge an entry fee per project. The project stays a draft until the fee is paid or waived.",
                requires_features=hackathons),
        feature("events.paid_teams", "events", "Paid team registration",
                "One fixed price per team, paid once by the team leader after the team is confirmed.",
                requires_features=hackathons),
        feature("events.saved_views", "events", "Saved views and exports for event lists",
                "Save filters on the guest, team, submission, results and judging-progress lists, and export "
                "exactly the filtered rows as CSV."),
        feature("events.gallery_search", "events", "Gallery search and awards",
                "Search and sort the public project gallery, filter award winners and show award badges once "
                "results are published.", default_enabled=True, requires_features=("events.project_gallery",)),
    )
