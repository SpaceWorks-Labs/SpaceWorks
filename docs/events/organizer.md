# Organizer and co-organizer runbook

**Pre-release: keep the programme off until [integration acceptance](integration-status.md).**
The steps below describe authored services and UI exports, not a verified deployed journey.
Missing required adapters deliberately refuse rather than invent an admission or permission.

1. Use an account with full event management to create the event, select organizers and
   venue, audience, tickets, dates and timezone. Invite co-organizers with only the event
   permissions you hold. A public event link does not grant management access. An ordinary
   event can keep using its existing registration workflow with hackathons off.
2. After acceptance of the deployment, enable the required Events features and configure the
   event's hackathon separately. Choose `solo`, `individual_then_team` or `team_together`.
   Team finder is an opt-in within `individual_then_team`, not a fourth team-mode enum.
   Solo forces team size one and disables finder. Set team size, application and submission
   windows, team lock time, attendance policy, upload policy and storage budget.
3. Publish a versioned code of conduct and require each applicant's own acceptance. Optional
   MLH data sharing is independent opt-in. Host waiver evidence is separate and follows the
   existing audience/collaboration policy. There is no minimum-age or guardian gate.
4. Build the application form through the shared form editor. Standard profile keys support
   reviewable Saved details prefill. Visibility and disclosure are server rules. Hidden
   answers are dropped; DOB/age cannot gate admission or another required answer. Saving
   answers to an applicant's account is their choice, never an organizer setting.
5. Choose auto, rolling or batch review; set N distinct reviewers, anchored rubric and
   optional blind view. Blind mode removes structured identity but cannot guarantee that
   free text is anonymous. Assign nonconflicted reviewers and replace recused/revoked ones.
6. Preview decisions, stage the private batch, then explicitly release that batch/version.
   Staging sends no notice and changes no participant admission or capacity. Release checks
   current reviews, authority, versions and roster. Cancelling a private batch sends nothing.
7. Monitor offers and RSVP deadlines. The default is four days **from committed release**.
   Offers reserve against an explicit offer ceiling; confirmation still needs a hard event
   and ticket seat. Overbooking offers never permits overfilling confirmed capacity.
   Team-together cohorts use people counts and confirm all members atomically after every
   member accepts. Expiry or decline releases the whole cohort. FIFO promotion can skip a
   group that does not fit. Extensions/on-behalf RSVP require a recorded reason and authority;
   they never accept a member's waiver or optional consent for them.
8. Configure volunteer-needed postings, shifts and requirements; approve contributors and
   assign mentors manually, round-robin or by skills. Check uncovered teams in the stored
   assignment result. Explicit contributor admission uses the normal registration/ticket
   service and a declared capacity policy; approving a role does not silently admit them.
9. Configure tracks, prizes, judging rounds and conflicts. Participants submit uploads **and**
   HTTPS links; links are not fetched by the server. A leader's submit creates an immutable
   snapshot with roster/assets/links/answers/tracks/prizes and hashes. Incomplete uploads
   cannot enter it. Triage changes eligibility; content amendment makes a new snapshot and
   requires a reason. Prior scores become historical rather than applying to new content.
10. Review judging coverage, ties and integrity flags. Weighted 1–5 or top-three ranking is
    implemented; pairwise is a chosen later feature. AI/reuse declarations and integrity
    flags inform review and never automatically disqualify. Finalize a result revision,
    then separately publish it. Corrections append history and do not restart retention.
11. Publish the gallery once using exact frozen items with live team consent. Granting
    consent does not publish. Any eligible sealed teammate can withdraw immediately;
    a later regrant needs an explicit manager amendment to become public again. Past-gallery
    access has its own gate and does not reopen an expired event website.
12. Choose certificate designs/library revisions and bulk subjects. Attendance does not need
    synthetic feedback; volunteer thanks needs independently verified positive minutes.
    Certificate verification requires an event policy plus certificate opt-in. It discloses
    event/date/valid-or-revoked only. Historical certificates are private until explicitly
    selected. Revocation/reissue uses the existing certificate service and keeps history.

For event-day doors, use the online credential scanner and saved desk badge design.
Check-in-only staff resolve minimal identity and print eligible attended rows; custom
answers need registration management **and** tenant audit permission. Resolution does not
mark attendance. Lost badges require rotation; ordinary member-profile QR is a different
credential. [Operator checks](operations.md#online-scanner-and-print-checks) must pass first.

Readiness and event-day summaries hide counts the actor may not see. Save, event publish
and website release remain distinct actions. Broadcasts save as drafts while you type and
require preview, current audience count and explicit confirmation. "Send now" waits five
seconds with an Undo; a scheduled send must be at least five seconds ahead. After the hold,
cancellation cannot retract messages a provider has accepted. Delivery tallies show how many
people each send reached, never who. With `events.broadcast_templates` on, start from one of
13 templates and pick the accent-band, photo-header or letter design. Series guests retain per-occurrence
permissions. Use only brand accent presets; review unsaved changes before navigation.

Before closing, check [media expiry](media.md#retention-and-removal), budgets, pending work
and cleanup failures. Turning a feature off retains history and owned objects. Purge is
destructive and is not a routine close-event step. The core payment ledger survives Events
purge. Travel reimbursement ([reimbursement](reimbursement.md)) and stage-triggered forms
([staged forms](staged-forms.md)) are built (owner decisions 34/35).

Routes: admin prefix `/api/v1/admin/events/{event_id}/`; `hackathon/`, `applications/`,
`application-decisions/preview|stage|release|cancel/`, `programme/readiness|live|publishing/`,
`forms/{form_key}/`, `results/preview|finalize|publish|correct/` and `gallery/` families.
Use the mounted OpenAPI for exact command schemas, selectors and methods; `|` here means
separate literal routes. Commands carry an operation UUID and expected version. A 409
requires reviewing current state, a 423 means source migration freeze, and a 503 means a
required provider is unavailable; do not bypass them with direct model writes.
