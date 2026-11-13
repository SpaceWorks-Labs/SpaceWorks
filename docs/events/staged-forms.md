# Staged event forms

Staged forms are mounted in the Events staff and member APIs and the event drawer's
**Stage forms** section. Definitions, assignments, revision-specific responses, milestones,
coverage guards and reconciliation use the same admission and check-in owners. This
guide describes the current contract; source integration alone does not establish
final browser, storage or migration acceptance.

Staged forms are an Events feature for ordinary events and hackathons, independent
of reimbursements. Forms reuse the shared forms engine and immutable form revisions.
Each participant receives their own assignment pinned to a published revision.

| Stage | Ordinary event | Hackathon |
| --- | --- | --- |
| Application | Registration submission | Application submission |
| Shortlisted | Explicit published checklist milestone | Explicit published shortlist |
| Accepted / RSVP | Registration confirmation | Released offer or confirmed RSVP |
| Before event | Eligible participant and scheduled opening | Eligible participant and scheduled opening |
| After event | Event ends and participant is eligible | Event ends and participant is eligible |

Viewing a context never creates an assignment, submission or notice. Ordinary
events do not acquire a separate RSVP state. Shortlisting does not approve a
registration, allocate a seat or change an admission decision.

A required form may block an explicitly configured later action. Missing assignment
coverage is incomplete even if a reconciliation worker has not run. A valid
completion requires the assignment's pinned revision and current submitted response;
an old submission cannot satisfy a replacement form. Server clock checks close
submission at the effective due time without waiting for a scheduled task.

Managers can explicitly extend or reopen a form with a reason. Cancelling an
assignment retains history and exempts that definition for that participant.
Reassignment pins a previously published revision, clears draft answers, gives a
reviewed future deadline and renews the requirement. Prior submitted revisions
remain intact; neither operation reverses a completed check-in or RSVP.

Staged forms reject DOB/age questions, mappings and derivations, including hidden,
optional or sensitive questions. DOB and computed age remain supported only on the
base registration/application form under the existing contract. Stage uploads accept
`stage_form_file` only; receipt and payment-routing files use separate finance contexts.

Saved details use the authorized owner-context mappings. Normal personal
fields default to saving; sensitive supported fields require explicit opt-in.
Staff receive only submitted answers that their live disclosure authority permits,
never vault values. Organizer detail needs registration-management plus host audit
authority; finance detail returns the separate sensitive-only projection.

Stage and RSVP reminders use the `ReminderSource` registry and shared sweep.
Deadline enforcement still uses the server clock when delivery is delayed or disabled.
The RSVP source does not require staged forms or reimbursement. Live delivery and
browser acceptance remain separate from source registration.
