# Mentor runbook

**Pre-release: complete [integration acceptance](integration-status.md) before operating.**
Mentoring requires `events.hackathons` and `events.mentoring`; check-in rounds additionally
require `events.mentor_rounds`. Assignment, queue access and event admission are independent.

1. Apply to or accept a mentor posting with your member account. Review form/CoC and optional
   Saved details choices. Approval grants only explicitly scoped current entitlements; it does
   not make you tenant staff, a judge, or an admitted attendee. Complete required training or
   briefing; waiver/CoC cannot be overridden.
2. Configure skills, private affiliations, capacity, availability and conflicts. An empty
   availability schedule can explicitly mean off duty. Declared conflicts must be current;
   a mentor relationship may also conflict with judging. A manager can propose manual,
   round-robin or skill assignments; activation rechecks current eligibility and capacity.
   Stored assignment runs include uncovered teams, including zero-coverage results.
3. Open the help queue when on shift. Unrelated queue readers see only safe alias/category/
   priority/zone summaries. Private body/comments require being the current assignee or
   an authorized manager; no applicant/contact directory is created. Teams and eligible
   mentors can raise help. Creating help does not claim it automatically.
4. Claim a ticket while eligible. One current claim, lease UUID/generation, request deadline,
   capacity, assigned priority window, skills and conflict checks prevent competing claims.
   Renew before expiry. If a lease is lost, reload before acting; a stale tab cannot resolve it.
5. Add private comments, resolve with a note, or release the claim when unavailable. Requesters
   may cancel or reopen their own eligible request; manager assignment/reopen needs its own
   authority. Expiry releases stale claims; terminal deadlines do not reopen through comments.
   Role end/off-duty changes close affected claims/mappings and future bookings through services.
6. Keep office-hour slots and bookings current. Teams book under real slot capacity and
   conflict checks. Team members can cancel their own future booking; staff cancellation is
   explicit and reasoned. Busy-mentor details and other teams' names are not disclosed.
7. In a configured check-in round, claim the team visit, heartbeat its live lease and submit
   the current form while that lease is valid. Fresh-eyes/conflict policies and explicit
   reasoned overrides apply. Prior notes are distinct from ratings; nominees require a
   completed non-away visit. An offline draft cannot acquire or substitute for a live lease.
8. Review private attention/coverage/analytics, respecting low-count and zero-variance
   diagnostics. Personal nudge mute is bounded. Practice runs never enter production
   results, certificates or notification outboxes.

Help notices carry only event ID, team alias, category, priority and authenticated navigation;
never private help text, answers, ratings or contacts. Current on-shift eligibility is rechecked;
15-minute attention targets organizers, with open-period generation deduplication. Delivery
adapters are still pending here, even though expiry/escalation/recovery jobs are registered.
Use the console as the operational record until delivery has been accepted.

Member help/office-hour routes live under
`/api/v1/member/makerspaces/{host_id}/events/{event_id}/help/` and `office-hours/`.
Delegated mentor console routes use `/api/v1/admin/events/{event_id}/` with exact
`mentor_queue`/management authority, including `help/`, `mentor-assignments/`,
`mentor-rounds/`, `mentor-analytics/` and the completion configuration routes.
Admin prefixes do not give a member JWT blanket admin access. Shift work and event door
attendance remain separate from visits; a badge scan never confirms all of them together.
