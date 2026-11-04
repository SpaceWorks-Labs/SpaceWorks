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
