"""NOT REGISTERED. Release-2 L21b views (judging rounds, finalists, prizes and payouts), pre-written
like pending_lanes; register them in events.py at merge with since = the new version.
The payout recipient is masked like a name; references, judge notes and criterion values never appear.
"""

from .types import Col, View

L21B_JUDGING = (
    View("judging_rounds", "events", "Judging rounds per event.",
         "FROM {events.JudgingRound} r JOIN {events.Event} e ON e.id = r.event_id", "e.makerspace_id", (
             Col("round_id", "r.id", "Round id."),
             Col("event_id", "r.event_id", "Event (events)."),
             Col("key", "r.key", "Round key."),
             Col("mode", "r.mode", "Scoring mode."),
             Col("state", "r.state", "Round state."),
             Col("visibility", "r.visibility", "What judges see."),
             Col("fresh_eyes", "r.fresh_eyes", "Judges new to the projects."),
             Col("advanced_from_id", "r.advanced_from_id", "Round its finalists came from (judging_rounds)."),
             Col("min_reviews", "r.min_reviews", "Reviews per project."),
             Col("opens_at", "r.opens_at", "Opens."),
             Col("closes_at", "r.closes_at", "Closes."),
         ), since=2),
    View("finalist_advances", "events", "Finalist advances from one round to the next.",
         "FROM {events.FinalistAdvance} a JOIN {events.Event} e ON e.id = a.event_id", "e.makerspace_id", (
             Col("advance_id", "a.id", "Advance id."),
             Col("event_id", "a.event_id", "Event (events)."),
             Col("source_round_id", "a.source_round_id", "From round (judging_rounds)."),
             Col("target_round_id", "a.target_round_id", "To round (judging_rounds)."),
             Col("selection", "a.selection", "Top N or hand-picked."),
             Col("top_n", "a.top_n", "N, for a top-N advance."),
             Col("created_at", "a.created_at", "Advanced."),
         ), since=2),
    View("judging_finalists", "events", "The projects each advance carried forward.",
         "FROM {events.JudgingFinalist} f JOIN {events.FinalistAdvance} a ON a.id = f.advance_id "
         "JOIN {events.Event} e ON e.id = a.event_id", "e.makerspace_id", (
             Col("finalist_id", "f.id", "Finalist id."),
             Col("advance_id", "f.advance_id", "Advance (finalist_advances)."),
             Col("snapshot_id", "f.snapshot_id", "Submitted project snapshot."),
             Col("source_rank", "f.source_rank", "Rank in the source round."),
         ), since=2),
    View("finalist_announcements", "events", "When finalists were announced.",
         "FROM {events.FinalistAnnouncement} n JOIN {events.Event} e ON e.id = n.event_id", "e.makerspace_id", (
             Col("announcement_id", "n.id", "Announcement id."),
             Col("event_id", "n.event_id", "Event (events)."),
             Col("advance_id", "n.advance_id", "Advance (finalist_advances)."),
             Col("published_at", "n.published_at", "Published."),
         ), since=2),
    View("hackathon_prizes", "events", "Prizes and their money per winner.",
         "FROM {events.HackathonPrize} p JOIN {events.Event} e ON e.id = p.event_id", "e.makerspace_id", (
             Col("prize_id", "p.id", "Prize id."),
             Col("event_id", "p.event_id", "Event (events)."),
             Col("name", "p.name", "Prize name."),
             Col("award_count", "p.award_count", "Winners."),
             Col("amount_per_winner", "p.amount_per_winner", "Money per winner."),
         ), since=2),
    View("prize_payouts", "events", "Prize payouts and reversals; the recipient is masked like a name.",
         "FROM {events.HackathonPrizePayout} p", "p.makerspace_id", (
             Col("payout_id", "p.id", "Payout id."),
             Col("event_id", "p.event_id", "Event (events)."),
             Col("prize_id", "p.prize_id", "Prize (hackathon_prizes)."),
             Col("recipient_id", "p.recipient_id", "Winner (members); masked unless member details are on.",
                 pii=True, pii_type="bigint"),
             Col("kind", "p.kind", "Payout or reversal."),
             Col("amount", "p.amount", "Amount."),
             Col("currency", "p.currency", "Currency."),
             Col("method", "p.method", "How it was paid."),
             Col("paid_on", "p.paid_on", "Paid on."),
             Col("ledger_entry_id", "p.ledger_entry_id", "Ledger entry (finance_ledger)."),
         ), since=2),
    View("judge_scores", "events", "When judge scores were saved and submitted (no values, no notes).",
         "FROM {events.JudgeScore} s JOIN {events.Event} e ON e.id = s.event_id", "e.makerspace_id", (
             Col("score_id", "s.id", "Score id."),
             Col("assignment_id", "s.assignment_id", "Judge assignment."),
             Col("saved_at", "s.saved_at", "Last saved."),
             Col("submitted_at", "s.submitted_at", "Submitted."),
         ), since=2),
)
