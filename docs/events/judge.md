# Judge and sponsor representative runbook

**Pre-release: real adapters and [acceptance checks](integration-status.md) remain pending.**
Use a member account with a current event/track/time-scoped assignment. Displaying a role
does not confer tenant authority or access to all projects.

1. Open your assignments and declare self, team, mentoring, affiliation and other conflicts.
   Recuse/skip explicitly instead of scoring conflicted work. Authority and conflicts are
   rechecked on reads and commands; do not retain private drafts after losing the assignment.
2. Judge the assigned **frozen submission snapshot**. Later project drafts and uploads are
   different content. Files use authenticated bounded readers; preview acceptance is
   [format-specific](media.md). Do not execute uploaded firmware/source/toolpaths.
3. For weighted scoring, use each anchored 1–5 criterion with its positive Decimal weight.
   For top-three ranking, rank distinct assigned projects. Small batches retain the fixed
   six-point budget rather than pretending every project received three views. Missing,
   skipped, recused or invalid work is not a zero score. Other judges' private notes are
   not your input.
4. Save drafts and submit using the current assignment/version. If content or eligibility
   changes, assignments become invalid and coverage must be rebuilt. A partially invalid
   ranking ballot loses its whole exposure; the system does not silently reweight it.
5. Organizers review view counts, workload/coverage, distributions, low-n/zero-variance
   warnings, configured tie-break priority and shared ranks. Finalization requires adequate
   coverage or a full-manager reason, integrity confirmation and explicit tie decisions.
   Optional z-score ordering is frozen into that calculation revision.

**Pairwise rounds** (switch `events.pairwise_judging`). You see one project at a time. The
first is only viewed; from the second on you answer "which was better: the one before, or this
one?" with **1** (before), **2** (now) or **S** (can't judge this one); **N** loads the next
project. Private notes go with each answer; declare a conflict from the "More" menu. Projects
come from your own track, room and batch scope only, never one you are conflicted with, and
never twice. Projects still below the round's comparison target come first. You never see
standings, so nothing anchors your choice. If two people judge at once, the page may say your
place changed: reload it and continue. The ranking is a full replay of every valid
comparison (crowd Bradley–Terry, written from Chen et al., WSDM 2013); a recusal or a changed
submission removes exactly the comparisons that showed that project. Each project needs at
least the round's minimum (three or more) valid comparisons, or a full-manager coverage
exception, before the round can be finalized. Nothing is published until the organizer
finalizes and then publishes results through the usual results step.
6. Result finalization and public announcement are separate. Corrections append immutable
   revisions. The first announcement anchors file retention; correcting results does not
   give files a fresh year. Gallery publication independently needs exact item consent.

Sponsor representatives get read-only submissions in their own track. A prize proposal
is not a judging score or final award. Résumé access additionally requires an explicit
live participant → named sponsor → recruiting-purpose grant tied to the current ready
event résumé and a matching frozen own-track project. Role-only contributors can consent
but are not downloadable without that project relationship. Replacement, deletion,
revocation, track/role loss or expiry denies new bytes, including old stream URLs.

No sponsor gets other sponsors' scores, judge notes, private form answers, an unconsented
participant directory, or Saved details vault access. Public cards/photos require a
participant's explicit selected public profile/scope; there is no private-avatar fallback.

Routes under `/api/v1/admin/events/{event_id}/` include `judge-assignments/`,
`judge-assignments/{assignment_id}/score|rank|recuse|skip/`, `judging-rounds/`,
`results/`, `sponsors/{sponsor_id}/submissions/` and
`sponsors/{sponsor_id}/resumes/{participant_asset_id}/`. Public gallery/results are under
`/api/v1/public/event-programmes/{public_token}/`. Consult mounted OpenAPI for exact
methods; authority is enforced server-side on every attempt and stream recheck.

## Judging extras

**Score next project.** In an open weighted round, "Score next project" opens a project you
already started, otherwise the eligible project with the fewest reviews. When the organizer sets
the round to "every project", it may hand you a project nobody assigned to you; it is then
assigned exactly like a planned one. A round may have a panel (only those judges score it) and
"fresh eyes" (you never get a team you reviewed in an earlier round). Each project still needs at
least three reviews.

**On your phone.** With an active judge, mentor, volunteer or crew role, the app can step your
session up to an event grant for that one event (attestation and your second factor, like a staff
step-up). It opens that event's desks and nothing else, and ends when your role ends.

**For organizers.**
- *Progress* lists projects below the review target, each judge's completion, scores more than two
  standard deviations from the project mean or more than 25 points apart (on a 0-100 scale), and
  drafts saved but not submitted for over a day.
- *Assignment* can be balanced, by track, by room or random. Random is seeded: preview, Re-roll for a
  new seed, then assign with the seed you previewed.
- *Finalists*: from a finalized round, preview the top N (ties at the cutoff all advance) or
  hand-pick projects, then advance them into a draft round, which opens on the finalists alone.
  Disqualified and withdrawn projects never advance. Publish finalists separately; the public
  results page shows them, finalists may get an email, and finalist certificates follow the
  publication. Results and prizes come from the final round.
- *Emails*: the results announcement and the submission receipt are per-event switches, off for
  new events. "Send results email now" sends it once for the published results.
- *Prize payouts*: set a prize amount per winner, then record each payout by hand after paying
  (record_payment or the Event Manager). Each payout is an expense in the finance ledger; a mistake
  is reversed, never edited. Nothing is paid automatically.

- *Scores CSV* (switch `events.scores_export`, off by default): one row per project per round with rank,
  reviews, raw and adjusted (z-score) score, one average per criterion and the judges who scored. It never
  carries comments, private notes, team feedback or email addresses; judge names show only to staff who may
  see personal data, otherwise "Judge 1, Judge 2". Every export is audited.
- *Reinstate*: a disqualified project can be reinstated with a reason. Its judging assignments come back
  (submitted scores were never deleted), except for a judge who now has a conflict, a finalized round or a
  pairwise round. An open entry-fee refund case is voided; once the fee was refunded or the refund approved,
  reinstating is refused (`fee_refunded`) because the project would stand submitted unpaid.
- *Unpublish results*: withdraw published results (refused once prizes were claimed or paid). Announcements
  not yet sent are cancelled; publishing again emails only people whose earlier message was cancelled, never
  anyone who already received it.
- *Assignment preview*: the dry run shows each judge's load before and after, and a `plan_fingerprint`. Send
  it back to apply exactly that plan (409 `plan_changed` if anything moved). `existing=keep` keeps current
  unscored assignments; `existing=replace` re-plans them (scored work is never touched).
- *Search*: the judge's own list takes `state` and `q` (project title) with a count per state; the staff
  results list and the public results page take `q` (project or prize).

Routes under `/api/v1/admin/events/{event_id}/`: `judging/scores-export/` (GET, CSV, `?round=`),
`results/unpublish/` (POST) and `submissions/{submission_id}/reinstate/` (POST).

Routes under `/api/v1/admin/events/{event_id}/`: `finalists/`, `finalists/preview/`,
`finalists/apply/`, `finalists/publish/`, `judging-rounds/{round_id}/progress/`,
`judging-rounds/{round_id}/next-project/`, `programme-options/`, `results/send-email/`,
`prize-payouts/`, `prize-payouts/{payout_id}/reverse/`, `lists/{list}/` and `lists/{list}/export/`.
The public gallery takes `q`, `sort` (`newest`, `az`, `awards`) and `awards=only`.
