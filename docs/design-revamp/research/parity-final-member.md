# Final functionality-parity audit: member area

Read-only audit. No app code was changed. Written 2026-10-16 against HEAD `b348ee18`.

- **Old** = `d3e5ed29`, read with `git show d3e5ed29:frontend/src/<path>`.
- **New** = working tree at HEAD.
- Scope: the signed-in member experience (`MemberArea` and every tab and section, the member account page,
  archived payments, claim redemption and claim session, member sign-in, the "Find a makerspace" list).
- Earlier checklist: `docs/design-revamp/research/parity-public-member.md` (member half, sections 16 to 20 and
  the S1 to S3 restore list).
- `cd frontend; npx vitest run src/features/members src/features/notifications src/features/bookings/MyBookings src/features/payments`
  passes: 45 files, 212 tests.

Status key: PRESENT (same capability, same place), BURIED (behind a tab, drawer or overflow menu, now at least
one extra click), CHANGED (behaviour, copy or default differs), MISSING (not reachable from any page). A
"BURIED (tab)" row is one click away and is the shell's deliberate design; only the rows listed in the restore
list need action.

## Summary

- **Counts (from the table below): PRESENT 71, BURIED 16, CHANGED 11, MISSING 0.** Rows marked "(new)" or
  "(absent in both)" are not counted.
- **No P0.** No capability is unreachable, no destructive action lost its confirmation (cancel application,
  cancel booking, cancel registration, leave makerspace, cancel renewal, revoke session, revoke calendar
  link all still confirm or take a second step) and no gate changed. The `memberTabs` gate, `accountSections`,
  `accountSelfService`, `canApply`, `membershipModuleOn`, verifier / vouch / referral gates and the
  self-service / self-export gates on `/member/account` are all identical to old.
- **One P1:** the new Events "Going / Past" split classifies by `starts_at`, so an event that has started but
  not ended, and its check-in QR, sits under "Past".
- **Earlier member restore-list items (10): 8 verified fixed, 2 still open (both P2, one accepted by design).**
  Details in "Earlier restore list status".

## Restore list (P0 to P2)

### P0

None.

### P1

**P1-1. Ongoing events and their check-in QR land in the "Past" tab.**
- Lost: a member opens Events at the event to show their check-in QR, but a registration whose `starts_at` has
  passed is filtered into "Past" (`MemberActivity.tsx:143`, `new Date(row.starts_at).getTime() < Date.now()`).
  Old listed every registration in one list (`MemberActivity.tsx:153` old), so the QR was always visible.
  The QR (`checkin_token`, `CheckInQr` at `MemberActivity.tsx:79`, rendered at :158) is the one thing a member
  needs on arrival, which is usually at or after the start time. They land on "Going", see nothing for the
  event, and must guess to open "Past".
- Why it matters: it is the highest-frequency use of the Events tab and fails exactly when needed. Check-in
  QR tokens are only issued for `registered` rows on checkable events (`member_activity_service.py:153-170`),
  so these are live, usable codes.
- Fix: the API already returns `ends_at` per registration
  (`backend/apps/makerspaces/member_activity_serializers.py:46`, `member_activity_service.py:195`) but the
  frontend `Registration` type (`MemberActivity.tsx:15-28`) does not declare it. Add `ends_at: string` and
  classify "past" with `new Date(row.ends_at).getTime() < Date.now()` at `MemberActivity.tsx:143`. Update the
  fixture in `MemberActivity.test.tsx` and add a started-but-not-ended case.

### P2

**P2-1. PWA install card says "Save your card below" but the offline-save control is no longer below it.**
`MemberInstall.tsx:24` renders on every tab; `OfflineCardSave` now lives only in the full card panel at
`?section=card` on Profile and card (`MemberCardPanel.tsx:121`, not rendered when `compact`). Old rendered the
card on the same Account tab. Fix: change the copy to "Save your card from Profile and card to read it
offline" and, when the membership is active, add a link to `{base}/account-portal?section=card`.

**P2-2. The empty state in the "Past" events tab is wrong.** `MemberActivity.tsx:160` (the `registrations.length ? ... : <EmptyState message="You're not registered for anything yet. See what's on." />` branch)
is shared by "Going" and "Past". Show "No past events yet." when `eventPeriod === "past"`.

**P2-3. Non-member overview header says "Join {name}" for members whose membership is revoked, suspended or
pending.** `MemberScreenLayout.tsx:21-25` keys only on `member` (= active). A revoked member legitimately sees
the join form (`canApply`), but a suspended or pending one sees "Join this makerspace" above their status card.
Fix: use the title "Your membership" when `membership` exists and is not revoked; pass a `hasMembership` prop.

**P2-4. Theme toggle is only in the user menu** (`UserMenu.tsx:12`). Old had a visible header toggle
(`MemberArea.tsx:132` old). Accepted by the shell pattern; earlier restore item 12, still open. Optional: add an
icon toggle to `MobileTopBar` for phones.

**P2-5. A failed bootstrap replaces the whole body with a retry card** (`MemberArea.tsx:159`, state `error`),
so a signed-out visitor loses the "Sign in to your account" button and the claim-code form while it shows. Old
rendered the error line and kept both (`MemberArea.tsx:186-189` old). The archived-payments recovery card is
preserved on purpose (the state only errors when `archivedUnknown` is false). Fix: keep the children rendered
below the error, or only show the error card when `!unauthenticated`.

**P2-6. "Cancel booking" is now inside the row's overflow menu** (`MyBookings.tsx:67`), "Reschedule booking"
stays a visible button (:66). The confirmation panel is unchanged (`MyBookings.tsx:70-74`). Used rarely; acceptable.
No change needed unless the owner wants it visible.

**P2-7. Member sign-in still has no "Forgot password?" link** (`MemberAuthPanel.tsx`; absent in old too, noted
in the earlier audit and never added). The reset flow exists at `/reset-password`. Add a link beside the
password label when `passwordLogin` is on. Enhancement, not a regression.

**P2-8. Inbox pagination assumes 24 per page** (`PersonalInbox.tsx:104` `pageSize: 24`); old used
`next`/`previous`. Earlier restore item 23, still open; safe while the API page size stays 24.

**P2-9. Receipts and credit notes are only reachable when the member has at least one payment row**
(`MemberArea.tsx:196` renders `MemberPaymentRows`, which hosts `PaymentDocuments`, only when
`paymentRows?.length`). Identical to old, so not a regression; a member whose only record is a receipt for a
charge that was later removed sees "Nothing to pay". Noted for completeness.

**P2-10. Save buttons on the profile forms only appear once the form is dirty** and are labelled "Save changes",
not "Save profile" (`MemberProfilePanel.tsx:236`, `MemberAccountProfile.tsx:15`, via `SettingsActions`).
Deliberate (shell pattern); recorded because a user looking for "Save profile" will not see a button until
they type.

## Earlier restore list status (member half of `parity-public-member.md`)

| # | Item | Status | Evidence |
|---|---|---|---|
| 6 | Bookings tab dropped the activity "Bookings" section | Fixed | `MemberArea.tsx:185` now includes `bookings`; `MemberActivity.tsx:154` renders the section |
| 7 | Presence button moved to header and vanished on list tabs | Fixed | inline button restored in the Presence card `MemberArea.tsx:180`, header primary kept `:160` |
| 12 | Theme toggle buried in user menu | Open, accepted | `UserMenu.tsx:12` (see P2-4) |
| 13 | Certifications literal "?" | Fixed | `MemberCertifications.tsx:18` uses " · Granted " |
| 14 | Preference centre literal "?" and duplicated label | Fixed | `PreferenceCentre.tsx:30` `legend` with " · " |
| 15 | "Loading your ticket?" and hard-coded "Space Works" on tickets | Fixed | `MemberActivity.tsx:119` ("Loading your ticket…", `organisation={organisation}`); no `organisation="Space Works"` remains in the tree |
| 17 | Non-member overview nested a full PublicLayout | Fixed | `MemberScreenLayout.tsx:21-25` uses `DashboardLayout` |
| 18 | User menu showed "Your account / Sign out" to signed-out visitors | Fixed | `MemberArea.tsx:154` shows "Not signed in" with "Sign in" |
| 19 | Workspace card showed an initial instead of the tenant logo | Fixed | `MemberArea.tsx:152` |
| 23 | Pagination assumes 24 per page | Open | `PersonalInbox.tsx:104` (P2-8) |

Also verified from sections 16 to 18 of that audit: Overview waiver banner (`MemberScreenLayout.tsx:26`),
Events QR modal, calendar actions in both Going and Past, partner-event tab, announcements tab, preferences tab,
Profile / Card / Certifications / Community / Invitations tabs, account page tabs and DangerZones.

## New behaviour worth recording (not counted)

- "Find a makerspace" (`MakerspaceDiscovery.tsx`, mounted `MemberArea.tsx:192`): central mode only, signed-in
  members only, Home tab only, hidden on a single-space domain; each row links to `/m/{slug}/member` and shows
  a Member / pending badge. The search box appears only above 6 spaces. It sits at the bottom of Home, below the
  membership card, so a member with a long Home page needs to scroll.
- Member shell gains Sign out (`MemberArea.tsx:156`), user-menu link to `/mfa` (:155) and "View public page"
  (`MemberPortalTabs.tsx:38`).
- Member card on Home as a compact ticket with "Show QR to scan" and "View your member card"
  (`MemberCardPanel.tsx:60-69`, `ScanQrView.tsx`).
- Directory search (`MemberDirectory.tsx:66`) and profile drawer.

## Responsive notes (below 768px)

- Navigation: 7 member tabs become a bottom bar of 4 plus "More" (opens the drawer with all 7), the active tab
  swapped in when it is not among the first four (`BottomTabs.tsx:6-7`). Every tab stays reachable.
- Header `secondary` actions are `hidden md:block` (`PageHeader.tsx:24`) and move into the header overflow
  menu on phones. On the Account tab that is "Account & security →" / "Two-step sign-in". It is not lost:
  the same two links are also rendered in the page body (`MemberArea.tsx:162`, `:174`), so phones keep a
  visible button.
- `ListRow` never hides its `right` slot (wraps beneath the title); renew, cancel registration, feedback, QR,
  pay now and generate-link actions all stay visible.
- Section tabs on Loans, Events, Inbox, Account, and the account page use the layout tab strip on every width.
- No `hidden` / `max-md:hidden` class removes any member capability. The only `hidden` elements are the
  honeypot field (`InvitationRequestForm.tsx:66`), the invisible submit buttons for Enter-to-submit
  (`MemberAuthPanel.tsx:141,178`), the inactive partner-events panel (`MemberArea.tsx:190`, which is
  `hidden` only while another Events tab is selected) and landscape-only copy in `ScanQrView.tsx`.

## Full capability table

### Shell, session and sign-in

| Capability | Old | New | Status | Note |
|---|---|---|---|---|
| Restore session on load | MemberArea.tsx:58,128 | MemberArea.tsx:145 | PRESENT | Loading card |
| Claim-session hand-off screen | MemberArea.tsx:129 | MemberArea.tsx:146 | PRESENT | Now carries the makerspace name and logo |
| Member sign-in panel (`showSignIn`) | MemberArea.tsx:130 | MemberArea.tsx:147 | PRESENT | `AuthLayout`, tenant brand passed |
| Sign in / Create account switch (only when self-serve) | MemberAuthPanel.tsx:218-221 old | MemberAuthPanel.tsx:146-148 | PRESENT | Segmented control |
| "Space does not run self sign-up" notice | :222-226 old | MemberAuthPanel.tsx:153 | PRESENT | `legal` slot |
| Sign-up fields (name, phone optional, email, password) | :188-204 old | MemberAuthPanel.tsx:158-170 | PRESENT | Adds strength meter |
| Password login switch hides the password field | :205-210 old | MemberAuthPanel.tsx:160-166 | PRESENT | |
| Email verification code, verify, resend | :131-169 old | MemberAuthPanel.tsx:129-141 | PRESENT | |
| MFA challenge after password or social | :129 old | MemberAuthPanel.tsx:127-128 | PRESENT | |
| Social sign-in (member surface, slug) | :228-237 old | MemberAuthPanel.tsx:149-152 | PRESENT | |
| "Forgot password" on member sign-in | absent | absent | (absent in both) | P2-7 |
| Tab navigation (7 tabs, module-gated) | MemberPortalTabs.tsx:26-53 old | MemberPortalTabs.tsx:11-21,37-46 | CHANGED | Sidebar and bottom tabs; `memberTabs` gate unchanged; "Overview" renamed "Home"; arrow-key roving removed |
| Theme toggle | MemberArea.tsx:132 old | UserMenu.tsx:12 | BURIED | P2-4 |
| Sign out | none | MemberArea.tsx:156 | (new) | |
| SupportContact | MemberArea.tsx:197 old | MemberArea.tsx:226 | PRESENT | |
| "Sign in" link to `/admin` when memberships query fails | :187 old | MemberArea.tsx:217 | PRESENT | |
| "Sign in to your account" button when signed out | :189 old | MemberArea.tsx:219 | PRESENT | |
| Error line (bootstrap, memberships, request, accept, presence, activity, checkout) | :186 old | MemberArea.tsx:216 | PRESENT | |
| Bootstrap failure | :166 old | MemberArea.tsx:159 | CHANGED | Whole body becomes a retry card (P2-5) |
| Archived-payments cards (found / "Closed makerspace?") | :137-138 old | MemberArea.tsx:163-164 | PRESENT | Same 404-tombstone logic |
| "Find a makerspace" list | none | MakerspaceDiscovery.tsx | (new) | |

### Home (overview)

| Capability | Old | New | Status | Note |
|---|---|---|---|---|
| PWA install card | MemberArea.tsx:134 old | MemberArea.tsx:161 | CHANGED | Every tab; copy "below" is stale (P2-1) |
| Join form with admission conditions (`AdmissionJoin`) | :142 old | MemberArea.tsx:168 | PRESENT | |
| Join CTA when module off (`JoinMembershipCta`) | :142 old | MemberArea.tsx:168 | PRESENT | |
| Ask for an invitation form | :143 old | MemberArea.tsx:169 | PRESENT | Honeypot kept |
| Own application status, cancel application, download data | :144 old | MemberArea.tsx:170 | PRESENT | `MemberAdmission.tsx` |
| "Membership request sent" | :145 old | MemberArea.tsx:170 | PRESENT | |
| Own application load error | :145 old | MemberArea.tsx:171 | PRESENT | |
| Staff-issued claim code redemption | :146 old | MemberArea.tsx:172 | PRESENT | |
| Non-member overview wrapper | :132-197 old | MemberScreenLayout.tsx:21-25 | CHANGED | P2-3 copy |
| Membership status card (space, status, role) | :147 old | MemberArea.tsx:173 | PRESENT | |
| Waiver text and Accept waiver / "on file" | :149 old | MemberArea.tsx:175 | PRESENT | Adds a banner linking to `#current-waiver` |
| Member verifier panel (`can_verify`) | :150 old | MemberArea.tsx:176 | PRESENT | Same gate |
| Vouch for applicant (`join_mode === vouch`) | :151 old | MemberArea.tsx:177 | PRESENT | Same gate |
| Presence status and Start 2-hour / End presence | :152 old | MemberArea.tsx:178-180, :160 | PRESENT | Inline button restored plus header primary |
| Needs-your-attention notices | :154 old | MemberArea.tsx:182 | PRESENT | |
| Checked-in state, waiver warning (My activity) | MemberActivity.tsx:149 old | MemberActivity.tsx:148 | PRESENT | |
| 3D print and machine-service requests | :150 old | MemberActivity.tsx:153 | PRESENT | |
| Recent presence sessions | :154 old | MemberActivity.tsx:161 | PRESENT | |
| Membership plan term and "borrowing paused" | :158 old | MemberArea.tsx:186 | PRESENT | |
| Compact member card with QR | none | MemberArea.tsx:187 | (new) | |
| On-loan, overdue and booking stat cards, overdue banner | none | MemberScreenLayout.tsx:27-30 | (new) | |

### Loans

| Capability | Old | New | Status | Note |
|---|---|---|---|---|
| Offline loans control | MemberActivity.tsx:148 old | MemberActivity.tsx:147 | PRESENT | "Out now" |
| Active hardware loans with due and overdue | :150 old | MemberActivity.tsx:149 | PRESENT | |
| Renew a loan | MemberLoanRenew (unchanged) | MemberActivity.tsx:149 | PRESENT | Same component |
| Request history and returned items | MemberArea.tsx:160 old | MemberArea.tsx:189 | BURIED | "History" tab (`?section=history`) |
| "Active membership required" notice | :190 old | MemberArea.tsx:220 | PRESENT | |
| Loading and empty states | :192 old | MemberArea.tsx:222, MemberActivity.tsx:149 | PRESENT | |

### Bookings

| Capability | Old | New | Status | Note |
|---|---|---|---|---|
| Upcoming and past booking list with timezone and cut-off | MyBookings.tsx:56-70 old | MyBookings.tsx:58-68 | PRESENT | `Tabs` |
| Private calendar feed (create, rotate, revoke) | BookingCalendar.tsx (old) | BookingCalendar.tsx | PRESENT | Same component |
| Reschedule booking | MyBookings.tsx:71 old | MyBookings.tsx:66, BookingReschedule.tsx | CHANGED | Now a modal |
| Cancel booking with confirm / keep | :72,:77-80 old | MyBookings.tsx:67,70-74 | BURIED | Overflow menu (P2-6) |
| Activity Bookings section (upcoming / past) | MemberActivity.tsx:152 old | MemberActivity.tsx:154 (rendered via MemberArea.tsx:185) | PRESENT | Restored |
| Loading, error with retry, empty, paging | :61-63,:81-85 old | MyBookings.tsx:59-61,74-77 | PRESENT | |

### Events

| Capability | Old | New | Status | Note |
|---|---|---|---|---|
| Registration list (status label, "no payment until confirmed", waitlist position) | MemberActivity.tsx:153 old | MemberActivity.tsx:143,157 | CHANGED | Split into Going / Past by `starts_at` (P1-1) |
| Show check-in QR | :78-119 old | MemberActivity.tsx:79-122 | CHANGED | Modal ticket; sits under Past once the event starts (P1-1) |
| Cancel registration with cutoff | MemberEventCancel (unchanged) | MemberActivity.tsx:159 | PRESENT | |
| Feedback and certificate | MemberEventFeedback (unchanged) | MemberActivity.tsx:159 | PRESENT | |
| Calendar subscription link (create, rotate, revoke, copy) | :153 old | MemberActivity.tsx:155 | PRESENT | Shown in both tabs |
| Partner (collaborative) events: register, apply, ticket, invite code, promo code, host waiver, custom form, contact fallback | PartnerEvents.tsx:146-219 old | PartnerEvents.tsx:143-215 | BURIED | "Partner events" tab, listed only once rows exist; registration form is a modal |
| "No events yet" and "See events" link | none | MemberActivity.tsx:160 | (new) | |

### Payments

| Capability | Old | New | Status | Note |
|---|---|---|---|---|
| Membership fee and outstanding per currency / unavailable / nothing outstanding | MemberDashboardSections.tsx:52-77 old | MemberDashboardSections.tsx:39-56 | PRESENT | Stat cards |
| Payment list with due-date filter, subject, status, due badge, amount | MemberPayments.tsx old | MemberPayments.tsx:30-42,83 | PRESENT | |
| Pay now (hosted `checkout_url`) | :34 old | MemberPayments.tsx:67 | PRESENT | |
| Generate payment link | :41 old | MemberPayments.tsx:69-80 | PRESENT | Same endpoint, same redirect |
| Pay at the space (no online rail) | :53 old | MemberPayments.tsx:44 | PRESENT | Same condition |
| Received-by settlement and refunds (succeeded / pending, reason, method, reference) | :60-85 old | MemberPayments.tsx:45-62 | PRESENT | |
| Receipts and credit notes (show, hide, Download PDF, paging) | PaymentDocuments.tsx old | PaymentDocuments.tsx | PRESENT | Only reachable with at least one payment row, as before |
| No-match message for the due filter | none | MemberPayments.tsx:83 | (new) | |
| Archived payments route `/member/archived` | ArchivedPayments.tsx old | ArchivedPayments.tsx | PRESENT | 404 tombstone, sign-in, per-space payments, settle, receipts |
| Loading, empty ("all settled") and error | :193-195 old | MemberArea.tsx:223-225 | PRESENT | |

### Inbox and notifications

| Capability | Old | New | Status | Note |
|---|---|---|---|---|
| Activity-derived notices and empty line | MemberArea.tsx:154,191 old | MemberArea.tsx:182,221 | PRESENT | "Notices" tab |
| Announcements feed with paging | AnnouncementFeed.tsx old | AnnouncementFeed.tsx | BURIED | "Announcements" tab; same gates (`member_inbox` and `membership.broadcasts`) |
| Personal inbox rows, unread count, Open link, Mark read | PersonalInbox.tsx:39-70 old | PersonalInbox.tsx:70-98 | PRESENT | |
| Mark all read | :50-51 old | PersonalInbox.tsx:74 | PRESENT | Header primary |
| Unread-only filter | :42 old | PersonalInbox.tsx:46 | CHANGED | Unread / All tabs |
| Family filter | :44-49 old | PersonalInbox.tsx:77 | CHANGED | Filters control; reachable on phones |
| Paging | :66-68 old | PersonalInbox.tsx:104 | CHANGED | Numbered, assumes 24 (P2-8) |
| 60-second auto-refresh, live updates | :29-31 old | PersonalInbox.tsx:58,60; MemberNotifications.tsx:9 | PRESENT | |
| Preference centre (family x channel toggles, mandatory events, digest) | PreferenceCentre.tsx old | PreferenceCentre.tsx:30-36 | BURIED | "Preferences" tab, same feature gates |

### Account (Profile and card tab, `/member/account-portal`)

| Capability | Old | New | Status | Note |
|---|---|---|---|---|
| Manage two-step sign-in link (`/mfa`) | MemberArea.tsx:136 old | MemberArea.tsx:162 | PRESENT | Plus header secondary and user menu |
| Manage your account link (gated) | :148 old | MemberArea.tsx:174 | PRESENT | Same gate (`member_accounts` and self-service or self-export) |
| Member profile (directory visibility, attended events, avatar, headline, bio, institution, interests, languages, GitHub, projects) | MemberProfilePanel.tsx old | MemberProfilePanel.tsx | BURIED | "Profile" tab; Save bar only when dirty (P2-10) |
| Member card: number, status, print count, issued date | MemberCardPanel.tsx:56-113 old | MemberCardPanel.tsx:60-67 | BURIED | "Card" tab; also compact on Home |
| Edit printed name, Save name | :69-90 old | MemberCardPanel.tsx:84-94 | PRESENT | |
| Preview card (PDF) | :91-100 old | MemberCardPanel.tsx:95-107 | PRESENT | |
| Card photo upload with consent | CardPhotoUpload.tsx | CardPhotoUpload.tsx | PRESENT | |
| Save card for offline use | OfflineCardSave.tsx | MemberCardPanel.tsx:121 | PRESENT | Only in the full card panel (P2-1) |
| Certifications (module `machines`) | MemberActivity.tsx:155 old | MemberArea.tsx:183 | BURIED | "Certifications" tab |
| Member directory with profile detail | MemberDirectory.tsx old | MemberArea.tsx:191 | BURIED | "Community" tab; detail in a drawer; search added |
| Send a referral | MemberReferrals.tsx old | MemberArea.tsx:197 | BURIED | "Invite a friend" tab, same gate |
| Claim a pending invitation with application answers | MemberReferrals.tsx old | MemberArea.tsx:197-213 | BURIED | "Invitations" tab; same outcomes and copy |
| Verify-email hint for invitations | MemberReferrals.tsx old | MemberReferrals.tsx:74 | PRESENT | |

### Member account page (`/member/account`)

| Capability | Old | New | Status | Note |
|---|---|---|---|---|
| Back to membership | MemberAccountPage.tsx:41 old | MemberAccountPage.tsx:52 | CHANGED | Header "Profile & card →" plus sidebar and user menu |
| Sign-in fallback and session restore | :40 old | MemberAccountPage.tsx:47 | PRESENT | |
| "Left this makerspace" and claim-session notices | :44-45 old | MemberAccountPage.tsx:55-57 | PRESENT | |
| "Account self-service is disabled" | :47 old | MemberAccountPage.tsx:58 | PRESENT | |
| Profile (display name, first, last, phone) | MemberAccountProfile old | MemberAccountPage.tsx:59 | BURIED | "Profile" tab; gated on `selfService` |
| Sessions and devices (list, current marker, legacy note, revoke, paging) | MemberAccountSessions old | MemberAccountPage.tsx:60 | BURIED | "Security" tab; adds a two-step link |
| Cancel renewal and Leave makerspace with reason and confirm | MemberAccountMembership old | MemberAccountPage.tsx:61 | BURIED | "Membership" tab; DangerZone then reason form then confirm |
| Data export (request, list, prepare link, download ZIP, paging) | MemberAccountExports old | MemberAccountPage.tsx:62 | BURIED | "Your data" tab; gated on `selfExport` |
| Self-service and self-export gates | :27-28 old | MemberAccountPage.tsx:44-45 | PRESENT | Identical |

### Claim sessions

| Capability | Old | New | Status | Note |
|---|---|---|---|---|
| Redeem a staff-issued claim code | MemberClaimRedemption old | MemberArea.tsx:172 | PRESENT | |
| Temporary session: waiver text, presence start / end, certifications, activity, "Browse tools" | MemberClaimSession.tsx old | MemberClaimSession.tsx:31-43 | PRESENT | Standalone `DashboardLayout` |
| Claim sessions blocked from account self-service | MemberAccountPage.tsx:45 old | MemberAccountPage.tsx:57 | PRESENT | |

## Counting method

Counted with:

```
grep -c "| PRESENT |" / "| BURIED |" / "| CHANGED |" / "| MISSING |"  docs/design-revamp/research/parity-final-member.md
```

over the "Full capability table" section only. The summary line above uses those numbers.
