# Decisions: Events and community

Part of the [decisions index](../decisions.md). Newest first. Each entry keeps its reason.

### D-342 — Event link on machine use
- **Area:** events
- **Date:** 12 November
- **Decision:** Machine sessions, service requests, adapter sessions and bookings can always be linked to an event, given by the requester at submission (optional) or set, changed or cleared by the area manager when handling it, audited with before and after. There is no switch and no per-type required option; event staff see machine use and consumables per event, and cost is charged to the event budget only after an organiser approves.
- **Why:** The maintainer wanted machine use logged against events; the earlier switch design was replaced by always-available linking.
- **Status:** current

### D-315 — Certificates share the Card Studio engine
- **Area:** events
- **Date:** 11 November
- **Decision:** Event certificates move onto the same document format, renderer and studio UI as cards, with certificate-specific layers (signatures, seals, serial and verification QR). Existing templates migrate losslessly and approvals, consent and verification behave as before.
- **Why:** One engine avoids two diverging designers.
- **Status:** current
- **Implemented in:** `backend/apps/events/certificates/`

### D-296 — Hackathon flow reviewed end to end
- **Area:** events
- **Date:** 11 November
- **Decision:** The whole hackathon journey (setup, admission, teams, submissions, mentoring, judging, results, certificates, prize claims and payouts, reimbursement through the ledger, notifications, exports, permissions, privacy) is reviewed for every role with fixes and tests.
- **Why:** Reason not recorded
- **Status:** current
- **Implemented in:** `backend/apps/event_reimbursements`, `backend/apps/events`

### D-294 — Events parity: badge engine and designer
- **Area:** events
- **Date:** 11 November
- **Decision:** The Events badge designer is its own UI on a `badge_v1` document format stored in the card engine and compiled to layers on save, with per-role designs through `card_role` (crew, volunteer, speaker, mentor, judge, organiser), a check-in QR kind that never rotates, 6x4 stock and offline-safe desk print. Switches `events.badge_designer`, `events.badge_desk_print` and `events.role_badges` default on when Events is on; new limit key `event_badge_prints_monthly` defaults to none. Behaviour mirrors the Events app, with code written natively. Staff ID cards (roles shown, numbered, verifiable, revoked when staff access ends) are part of the card work. Seven source features were excluded with reasons.
- **Why:** Matches the proven badge workflow while fitting the shared card engine.
- **Status:** current
- **Implemented in:** `backend/apps/events/badge_templates.py`, `backend/apps/events/badge_desk.py`, `backend/apps/events/badge_prints.py`

### D-290 — ID cards and badges, and parity with the sibling apps
- **Area:** events
- **Date:** 11 November
- **Decision:** The card engine supports event attendee badges, crew and role badges, member and staff ID cards, with desk instant print (offline-safe; A6, 4x6, 3x4, CR80), bulk issue and A4 sheets with crop marks, single-card PDF/PNG, a public scan-to-verify page (valid/expired/revoked, name, status, expiry only), email and Apple/Google Wallet. Events badge design and the organization card design each keep their own designer, implemented natively. Parity with the sibling Events and Organization apps means every capability SpaceWorks needs, fitted into existing flows; features that do not fit are excluded with a one-line reason. Only Google's open fonts plus the free Gilroy weights ship; the source app's 66 card fonts are not ported.
- **Why:** Events and organizations need printable, verifiable credentials.
- **Status:** current
- **Implemented in:** `backend/apps/card_designs`, `backend/apps/id_programmes`, `backend/apps/events/badge_rendering.py`

### D-199a — ID cards and event certificates built to parity and beyond
- **Area:** events
- **Date:** 5 Nov 2026
- **Decision:** ID cards and event certificates are audited feature-for-feature against a public reference project (features only, no copied code or assets), every gap is closed, and extras are added: role/award variants, signatories with release approval, an anti-tamper verify QR, LinkedIn add-to-profile, bulk issue with preview, email delivery, revoke/reissue with audit, multi-language names; for cards a template gallery, snapping, Code128, photo filters and a calibration sheet. Cards are always free and the earlier owner rules (two codes, minimal verify) stand.
- **Why:** The maintainer asked for the best-in-class ID card and certificate experience.
- **Status:** current
- **Implemented in:** backend/apps/events/certificate_rendering.py, backend/apps/card_designs

### D-199b — ID card and certificate design rules
- **Area:** events
- **Date:** 6 Nov 2026
- **Decision:** Templates ship light and dark and two-sided; the dark theme recolours only text sitting on the card background. Barcodes are Code128 of the printed number or desk code, never the verify token; photo filters are none/greyscale/duotone applied server-side; italic is refused (no real italic face bundled). History keeps every revision and restore makes a draft. Signatory approval gates render and email, never issuance; signatories are active space members. Designs, kinds and signatories sit behind `events.certificate_designer`, while issue, download, share and verify belong to `events`. The holder name on the verify page and share image is opt-in and never shown when revoked.
- **Why:** Reason not recorded
- **Status:** current
- **Implemented in:** backend/apps/events/certificate_rendering.py, backend/apps/card_designs

### D-197h — People's choice and platform overview choices
- **Area:** events
- **Date:** 5 November
- **Decision:** People's choice: one changeable ballot until close, no voting for your own team, 20 votes per hour, voting only on final-stage gallery entries, ties all win, public counts only after publish, and the staff ballot list never shows choices; off returns 404 and keeps data. Platform overview: periods are UTC, utilisation is session hours over active machines times period hours, results are cached 10 minutes, reads are not audited but exports are, and directory-hidden spaces are excluded by default.
- **Why:** Small design calls recorded under the standing rule to take the recommended option.
- **Status:** current

### D-181 — Prize tax recording and people's choice award
- **Area:** events
- **Date:** 5 November
- **Decision:** Prize tax is record only: the winner's tax ID is collected encrypted (scoped PII), each payout stores gross, tax withheld and net, and a per-space deduction setting (default rate 30%, threshold 10,000, off by default) proposes the deduction; staff deduct and file outside SpaceWorks. People's choice is an optional per-event extra award where signed-in members vote on public gallery projects, one vote per person, results hidden until staff publish; it never replaces judging.
- **Why:** Reason not recorded
- **Status:** current

### D-180 — Hackathon stage extras and prize money
- **Area:** events
- **Date:** 5 November
- **Decision:** Stages gain late policies, per-team extensions, per-stage file limits and video hosts, custom-field visibility, resubmission modes, a presentation mode, entry fees per stage, and integrity flags. Money additions: refund cases for cancelled events and (opt-in) withdrawn or not-shortlisted teams, per-member prize splits with a winner claim flow, non-cash prizes with fulfilment, sponsor-funded prize pools, an optional refundable no-show deposit refunded only through a staff-approved batch, and clawback when a winner is disqualified after payout. Not applied because they would reverse earlier decisions: per-member team fees, charging before acceptance, automated prize transfers, deposit refunds without staff approval, cash travel advances and age rules.
- **Why:** Reason not recorded
- **Status:** current
- **Implemented in:** `backend/apps/events/submissions/stage_service.py`, `backend/apps/events/submissions/entry_fees.py`

### D-179 — Shortlist gates between stages
- **Area:** events
- **Date:** 5 November
- **Decision:** Any submission stage may end with a shortlist step where staff or judges pick who advances by hand or from a judging round (top-N with ties advancing). Only shortlisted teams submit the next stage; the others keep their earlier snapshots and are told by email (switchable). Results are audited, published once, and the public gallery never shows eliminated teams' unpublished work.
- **Why:** Reason not recorded
- **Status:** current
- **Implemented in:** `backend/apps/events/submissions/stage_shortlists.py`

### D-177 — Hackathon multi-stage submissions
- **Area:** events
- **Date:** 5 November
- **Decision:** Each event has submission stages (name, window, grace, optional "requires previous stage") with per-stage requirements: files and/or links mode, required link kinds, minimum and maximum files, accepted file families, custom required fields. Presets include Single submission (the default and backfill), Idea to Final, Idea to Prototype to Final, Hardware build, Design sprint, Ideathon, Case competition and a Full pipeline. Requirements are enforced at submit time (drafts may be incomplete), every stage submission is a frozen snapshot, judging rounds choose the stage they judge, and changes are audited. Merges the ledger's three decisions on submission content, stages and presets.
- **Why:** Organisers need to choose what participants must submit, and each stage needs its own deadline.
- **Status:** current
- **Implemented in:** `backend/apps/events/submissions/stage_presets.py`, `backend/apps/events/submissions/models_stages.py`, `backend/apps/events/submissions/stage_rules.py`

### D-128f — Applications and hackathon payment rules
- **Area:** events
- **Date:** 28 October
- **Decision:** Applications are available for any event, with judging of at least 3 and 1-20 application stages. Paid places are charged after confirmation rather than pay-to-accept, and freeing a place on "No" is a per-event switch off by default. For paid hackathon teams only the leader pays, once, and hackathon emails are per-event switches off for new events.
- **Why:** Reason not recorded.
- **Status:** current

### D-35 — Staged forms
- **Area:** events
- **Date:** 18 October
- **Decision:** Events and hackathons can attach forms to stages (application, after shortlist, after acceptance/RSVP, before event, after event) with deadlines, reminders and Saved-details autofill.
- **Why:** Reason not recorded.
- **Status:** current
- **Implemented in:** `backend/apps/events`

### D-21 — Organizer tooling gap list
- **Area:** events
- **Date:** 18 October
- **Decision:** A set of organizer features was adopted in full: layered certificate builder with bulk issue and template library, desk ID-card printing, form builder with show-if, broadcast composer, readiness checklist, event-day mode, analytics funnel, live ticket, short links, cover photo editor, publishing questions with an unsaved-changes bar, accent presets (brand palette only), leave-organization, security activity, series guest list and platform insights.
- **Why:** Reason not recorded.
- **Status:** current
- **Implemented in:** `backend/apps/events`, `backend/apps/events/short_links.py`

### D-16a — Submission files: scanning, previews, storage, retention
- **Area:** events
- **Date:** 18 October
- **Decision:** Virus scanning is an optional ClamAV service (off in dev, recommended in production). Video gets duration and resolution checks with no transcoding. Previews cover 3D formats and Gerber, with other CAD and KiCad files download-only. Each event has a storage budget, and submission files are deleted 365 days after results while records and hashes are kept.
- **Why:** Reason not recorded.
- **Status:** partly superseded by D-138
- **Implemented in:** `backend/apps/maker_formats`, `backend/apps/events/hackathons`

### D-10a — Mentors, volunteers and sponsors in hackathons
- **Area:** events
- **Date:** 18 October
- **Decision:** A mentor help queue is core, with optional check-in rounds and analytics; teams and mentors can both raise help requests, alerts reach on-shift mentors, and mentors are assigned manually, round-robin or by skill. Volunteers get "needed" listings, shifts with capacity and waitlist, approval, check-in/out, hours and a thank-you certificate. Sponsor reps see only their own track's submissions, and résumés only with explicit participant opt-in. Co-organizers can invite volunteers, mentors and judges only with permissions they hold.
- **Why:** Reason not recorded.
- **Status:** current
- **Implemented in:** `backend/apps/events/mentoring`, `backend/apps/events/volunteer_hours_adapter.py`

### D-5a — Hackathon review, judging, gallery and integrity
- **Area:** events
- **Date:** 18 October
- **Decision:** Applications get N reviewers with an anchored rubric and optional blind mode. Judging is a weighted 1-5 rubric or top-3 stack ranking (pairwise was added later). The public project gallery is published once by the organizer and shows only items teams mark public. Integrity uses an AI-use declaration and an optional "first commit before kickoff" flag that never auto-disqualifies. Code-of-conduct consent is required per hackathon and sharing fields are optional.
- **Why:** Reason not recorded.
- **Status:** current
- **Implemented in:** `backend/apps/events/hackathons`, `backend/apps/events/judging`

### D-1a — Hackathons are an opt-in part of Events
- **Area:** events
- **Date:** 18 October
- **Decision:** Hackathons are an opt-in feature inside Events, off by default per makerspace. Team formation (solo, individual-then-team, team-applies-together, team finder) is chosen per hackathon, submissions accept uploads and links including hardware files, and applications run as auto, rolling or batch with staged private decisions, RSVP deadline, waitlist and overbooking.
- **Why:** Reason not recorded.
- **Status:** current
- **Implemented in:** `backend/apps/events/hackathons`
