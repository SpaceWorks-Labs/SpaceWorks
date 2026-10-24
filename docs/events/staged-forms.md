# Staged event forms

Implementation status: **partial R2 implementation, unmounted**. Definition,
assignment, response, milestone, coverage-guard and reconciliation commands now
exist, together with owner UI and revision-specific detail routes. The Saved-details
dispatcher, canonical admission/check-in bridges, file transport/retention and
complete acceptance still require integration. New cursor models need G migrations.

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

Saved details must use F's mappings and P's authorized owner context. Normal personal
fields default to saving; sensitive supported fields require explicit opt-in.
Staff receive only submitted answers that their live disclosure authority permits,
never vault values. Organizer detail needs registration-management plus host audit
authority; finance detail returns the separate sensitive-only projection.

Reminder delivery must use the real `ReminderSource` registry and shared sweep.
Stage and RSVP ReminderSource adapters are supplied for G registration. Their
frozen identity vectors, live delivery and browser evidence remain unverified;
AO20 is open. The RSVP source does not require staged forms or reimbursement.
