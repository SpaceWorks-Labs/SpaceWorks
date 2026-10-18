# Account deletion privacy note

Self-service deletion/archive/restore/purge and Apple revocation apply only to member accounts.
Staff/platform accounts use administrator lifecycle services; separate accounts sharing email/phone
are never deleted or restored together.

Deleting a member account applies across every makerspace on this deployment. It requires a
fresh identity check and typing `DELETE`. All outstanding obligations must be settled
first; the account page lists blockers and links to the relevant screens. Accounts with
no usable verification method must contact their makerspace.

The account becomes inactive immediately. All sessions end, memberships are revoked,
open membership applications are closed, and sign-in credentials are disabled. Mutable
identity copies are archived for 90 days by default, then removed by the daily purge.
An operator may configure a different retention window. Frozen tenant migrations,
unavailable storage and pending Apple revocation can delay completion.

Before the purge deadline and before any identity removal starts, eligible accounts can
come back through password recovery (a one-use restore link valid for 24 hours) or,
for phone-only accounts, a restore code from phone sign-in. Both require a new password.
Accounts with neither email nor phone need a fresh sign-in from an already-linked
provider that proves when authentication happened; providers unable to prove freshness
cannot restore the account. The deletion confirmation tells you whether a usable
recovery path is available. Restoration does not reinstate memberships, grants, sessions
or push destinations. Once removal starts, it cannot be undone even if cleanup is delayed.

Purge clears account contact details, names and verified identity stamps, replaces the
username and display name with anonymous placeholders, removes social identities,
authentication challenges, password-reset envelopes, push destinations and personal
inbox rows, and deletes maker profiles/projects and their images. It scrubs contact
snapshots on hardware requests, bookings, event registrations and owned machine-service
requests; booking notes and custom answers; registration custom answers; membership
application answers and invitation addresses; and email-log recipients/content addressed
to the account or its address recorded when deletion was requested. Membership cards
are already revoked and redacted during immediate account closure. Canonical envelope bodies,
routing/context and account-bound proof receipts/mapping snapshots must be scrubbed by account
ID; optional-inbox push children require their envelope ownership path. Shared sender/STOP,
provider-reference and other accounts' protections survive. See the reconciliation rollout
checkpoints for the required cross-lane privacy-hook verification before activation.

The following records remain after account deletion:

- `AuditLog`.
- `Payment`, `Refund` and `ManualSettlement`.
- `PaymentDocument.payer_label`: the historical username; walk-in usernames may embed a name.
- `RequesterAccountability` and `ReturnEvent`.
- `EvidencePhoto` rows; photo bytes follow the separate evidence-retention policy.
- `MachineUsageEntry`, `EventAttendanceCertificate` and `EventFeedbackResponse`, protected by immutable triggers.
- Staff-addressed notification emails mentioning the member, until EmailLog's existing retention expires.
- `NotificationDeliveryLog` text, deleted by `notifications/retention.py` on its existing windows.
- Staff actor snapshots on other people's memberships.

Backups age out under their own retention. Restoring or importing deletion-requested
identities keeps them inactive and preserves their deletion timestamps; purged identities
remain anonymous.

For Sign in with Apple, the service attempts to revoke the stored refresh token for each
Apple client used by the account. Older sign-ins may have no stored token. If a token is
captured for revocation, recovery and a subsequent sign-in do not replace that queued
token: only the original token is revoked. If a token is
unavailable or revocation keeps failing through day 80, that outcome is audited and the
identity purge can complete. You can also remove Space Works under **Sign in with Apple**
in your [Apple Account settings](https://account.apple.com/account/manage).

Operators should include these facts and their configured retention periods in the
deployment's published privacy notice.
