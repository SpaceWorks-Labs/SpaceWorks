# Participant and team runbook

**Pre-release: these workflows await [integration acceptance](integration-status.md).**
Use them only after the organizer confirms the programme is available on the deployment.

1. Open the public event link and sign in with your member account. The authenticated
   token context resolves the event and host; an accounts-audience event needs no host
   membership or existing application. Anonymous context requests require sign-in.
   Member/invite audiences retain their own eligibility rules. Reading context or your
   virtual first draft creates no application, registration, saved value, charge or QR.
2. Select an available ticket where required and review contact details. Existing account
   email/phone take precedence over fallback contact values; this form does not edit login
   identifiers. Supply invitation/promo codes only on submit. Review the exact current host
   waiver when applicable, and separately accept the hackathon code of conduct yourself.
   A leader cannot accept consent for other members. Optional MLH sharing can stay off.
3. Review prefilled answers and each “save to my profile” choice. Ordinary mapped details
   default on; DOB, résumé, dietary/accessibility needs and emergency contact default off.
   Hidden questions are omitted. Saving a draft does not update Saved details; a successful
   submit/edit can queue an account-owned save intent. Check its status: a conflict keeps
   your newer saved value rather than silently overwriting it. Organizers see submitted
   answers, not your account vault. The Saved details page lets you edit/delete fields and
   request a private export independently of membership.
4. If asked for age, review the age at the event's local start date. The encrypted DOB is
   the source; numeric age is never stored as the answer. A reschedule before answer lock
   requires date review; a locked revision keeps its frozen date. DOB is shown to organizers
   only if the form explicitly asks for DOB. There is no age-limit or guardian workflow.
5. Submit the reviewed form. Private staged review outcomes are not your result. Once an
   offer is released, RSVP before the displayed deadline (four days by default). An offer
   is not a confirmed place. Confirmation must still fit hard event/ticket capacity.
   For a team-together application, everyone accepts independently and the whole cohort
   confirms together; one decline/expiry releases the cohort. Waitlist consent is explicit.
6. Build your team according to the configured mode. Solo makes a one-person team;
   individual applications can form teams and opt into finder; team-together applications
   seal their roster for cohort review. Finder cards are opt-in and do not expose contacts.
   Invitation secrets travel in the URL fragment and are single-use; share privately and
   rotate a lost invitation. Joining/leaving, leadership succession and cancellation stop
   when the roster is locked. Team comments are private to current team members.
7. Add project details, AI/reuse declarations, tracks/prizes, ready uploads and HTTPS links.
   [Media rules](media.md) give file/group limits and preview availability. Do not run
   uploaded firmware, source code or toolpaths merely because the platform accepted a file.
   Wait for validation/scan/probe completion before submit. Resume interrupted multipart
   work through the authenticated upload controls; expired grants need fresh authorization.
8. The leader submits before the deadline. Submission freezes the eligible roster and exact
   content; later drafts/uploads do not change judges' snapshot or the public gallery.
   Withdrawing a submission is distinct from withdrawing the event application. A staff
   content amendment requires a reason and a new immutable snapshot with judging invalidation.
9. Choose project metadata and individual assets/links for gallery publication. Consent alone
   never publishes. Any eligible active sealed teammate can make it private immediately.
   A later grant does not revive an old public URL. Sponsor résumé sharing is a separate,
   named sponsor/recruiting opt-in tied to your current ready event résumé. Uploading a
   résumé or joining a team never grants sponsor access; revoke through your own consent page.
10. Select a profile photo only if wanted. Choose your own active membership profile explicitly
    (including an eligible profile from another space), or no photo. Print consent and public
    card consent/scopes are separate. Private accounts/staff pictures are never fallback photos.
    Losing public-profile eligibility removes the public card/photo. Vault résumé deletion
    does not delete an independently owned résumé already submitted to an event.

At the door, present your current event ticket/badge QR. It identifies you only to an
authorized online scanner for that event. Reading/scanning it does not itself mark attendance;
staff confirmation does. Rotation invalidates a lost badge. A v2 badge cannot be used with
offline/station roster shortcuts. The ticket's attended state follows saved attendance and undo.

Certificates remain private downloads. If the organizer explicitly enables public verification,
its QR/ID page reveals only event, event date and valid/revoked status, without your name,
PDF or revocation reason. Share that ID knowing the event/date become readable. Badges with
check-in secrets are never sent as personal-chat PDFs or posted into staff rooms.

Route guide: authenticated token context is
`GET /api/v1/public/event-programmes/{public_token}/context/`; owner commands are under
`/api/v1/member/makerspaces/{host_id}/events/{event_id}/` (`application/`, `teams/`,
`team-finder/`, `participant-resumes/`, `resume-consents/`, `presentation/`). Global
Saved details is `/api/v1/member/saved-details/`. Keep operation UUIDs when retrying a lost
response; changed input needs a fresh operation. Review stale form/date/version errors
instead of reposting a computed age or overwriting a newer server state.
