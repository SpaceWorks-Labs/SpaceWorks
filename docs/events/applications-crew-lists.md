# Applications, review stages, attendance, crew and check-in lists (release 2 L21a)

Six Events capabilities, all off by default, all keeping their data when turned off. The rules
behind each are in `docs/INVARIANTS.md` ("Applications, review stages, attendance, crew and
check-in lists").

## Applications for any event (`events.applications`)

1. Turn on **Applications for any event** in the space's Features.
2. Open the event, then **More > Programme setup**: write the code of conduct and the application
   form, choose auto, rolling or batch review and enable applications. Without Hackathon
   programmes on, the event runs in solo mode: no teams, team finder or project submissions.
3. Applicants apply from the event page; staff review under **More > Applications**, stage a
   private decision batch and release it. Offers are answered by RSVP. A paid place is charged
   only after the applicant confirms, exactly as for any other registration.

## Review stages (`events.application_stages`)

1. Under **More > Applications**, **Review stages**, add stages in order. Each has 1 to 20
   reviews per application, up to ten criteria scored 1 to 5 and an optional blind review.
   These three freeze when the stage gets its first review.
2. **Panel and assignment**: pick the reviewer panel, choose Balanced or Random, **Preview**,
   then **Apply this plan**. The seed is kept so the plan can be reproduced; if applications
   or the panel changed since the preview, apply refuses and asks for a new preview.
3. **Open for review.** Panel reviewers work at **Member > Application reviews**
   (`/member/application-reviews`); they see only their own assignments and nothing else of
   the event. This workspace is web-only until native event-role sign-in exists (#173).
4. Select applications in **Progress** and **Advance selected to the next stage**, or stage an
   offer, waitlist or rejection as usual. A decision staged against an application that has
   since moved is skipped at release and recorded in the audit log.
5. Optional: tick the per-event "stage advanced" email under Participation settings.
6. Travel support can require a stage: set `min_application_stage` on the reimbursement
   programme; requests are accepted once the application stands in that stage or later.

## Attendance confirmation (`events.attendance_confirmation`)

1. Under **More > Broadcasts**, **Are you still coming?**: **Ask everyone not yet asked**,
   later **Remind people who have not answered**. Sends are at least 12 hours apart and are
   never automatic.
2. People answer on their own page (`/member/events/<event>/attendance`) with an optional note.
   Replies show in the guest list, at the desk and in the registration export.
3. Optional per event: **Free the place when someone answers No**. A free place goes to the
   waitlist; a paid place is cancelled under the refund policy and any refund waits for staff
   approval; a seat bought in a group order is left for staff.

## Re-accepting a declined registration

In the guest list, a rejected registration shows **Re-accept** when a place is free. A paid
registration gets a new charge; send the pay link or collect at the desk.

## Crew (`events.crew`, `events.crew_claims`)

1. **More > Crew**: open the sign-up link (`/member/events/<event>/crew`), choose whether each
   sign-up needs review, and whether opted-in crew with a public profile appear on the event page.
2. Approve or decline sign-ups, or add people directly. Each approved crew member gets a free
   crew place that never uses capacity, is never charged and carries a crew chip.
3. Crew get no staff access from being crew; a desk still needs its own role.
4. The catering summary counts dietary needs; it never shows who has which.
5. With **Crew expense claims** (needs Event reimbursements), crew request and claim expenses
   through travel support; payouts go through the expense ledger.

## Check-in lists (`events.checkin_lists`)

1. **More > Check-in lists**: create a swag, meal or workshop list. Optionally only after entry
   check-in, or only for buyers of an add-on (each unit bought allows one collection).
2. **Collect**, enter the registration number and **Record collection**. Lists never change
   entry check-in. Archive a list to make it read-only. Online only.
