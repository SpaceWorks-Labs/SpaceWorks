# Volunteer runbook

**Pre-release: [integration and browser acceptance](integration-status.md) are pending.**
An approved contribution is event-scoped work, not a built-in staff role or automatic ticket.

1. Read the event's visible “volunteers needed” posting: task, dates, requirements and shift
   availability. Use your member account; you need not become a tenant staff account.
2. Open the posting application, review the shared form/CoC, Saved details choices and any
   age-at-event date review. Sensitive save choices default off. Only your submitted answers
   reach the organizer. Drafts create no grant. Submit, then wait for approval or the posting's
   explicitly configured auto-approval policy.
3. If invited, accept or decline explicitly. Approval needs current issuer authority, requirements
   and consent; imported roles are inert until reconfirmed. Co-organizers cannot invite you
   with permissions beyond their own scope/time window. A volunteer label alone grants nothing.
4. Choose a visible shift. Capacity, waitlist and overlapping work are checked under locks.
   Training/briefing exceptions require an exact reasoned staff record; no exception bypasses
   waiver or CoC. Role approval and attendee admission are separate: ask the organizer about
   the declared contributor ticket/capacity policy if you also need an event ticket.
5. Check in and out of the shift within its allowed window. Shift attendance does not secretly
   mark ordinary event attendance. Correct mistakes through the organizer; do not repeatedly
   check in to invent hours. Work evidence/corrections are retained and audited.
6. An authorized person other than you verifies/adjusts minutes. Thank-you certificate
   eligibility requires independently verified positive minutes, not a display role alone.
   Certificate rendering and delivery use the normal private issuance workflow.
7. Withdraw future work or decline an invitation when unavailable. Withdrawal/revocation
   removes derived authority and cancels affected future work; retained verified hours survive.
   Reopened answers need fresh review/consent, preserving the earlier locked revision.

Scheduled shift notices exist for one week before, two days before and event-local day-of;
past schedules are skipped. They must recheck shift version, approval, time window and
recipient at delivery. Actual programme delivery adapters remain pending in this checkpoint;
do not rely on a reminder arriving. Monitor your application/shift status directly.

Choose any badge/card photo through the separate selected-profile controls. No photo is valid.
An event credential is not proof of verified volunteer hours. Public cards need independent
public-profile and per-scope consent. For sponsor résumé sharing, use the canonical owner
consent workflow; contribution approval never opts you in.

Owner routes under `/api/v1/member/makerspaces/{host_id}/events/{event_id}/` include
`role-postings/`, `role-postings/{posting_id}/application/`, `role-applications/`,
`role-applications/{assignment_id}/submit|withdraw|date-review|decline|export/`,
`shifts/` and `shift-signups/{signup_id}/withdraw|check-in|check-out/`.
The suffix alternatives are separate routes. Approve, verify-hours and adjust-hours are
admin actions; there are no participant approval/verification aliases. Use OpenAPI for
exact methods and command bodies.
