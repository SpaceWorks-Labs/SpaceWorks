# Decisions: Security and authentication

Part of the [decisions index](../decisions.md). Newest first. Each entry keeps its reason.

### D-361 — Restricted accounts can sign in and refresh
- **Area:** security
- **Date:** 12 November
- **Decision:** Restricted or suspended accounts may sign in and refresh (normal MFA unchanged) into a session limited to the admitted route set, with a typed account-state field in the sign-in response. The GitHub callback fallback page has no analytics or replay, and association files are also served on the platform domain suffix host.
- **Why:** Members must be able to see and settle their own charges.
- **Status:** current

### D-351 — WhatsApp STOP is always honoured
- **Area:** security
- **Date:** 12 November
- **Decision:** A WhatsApp STOP message is accepted even while the tenant source gate is closed.
- **Why:** An opt-out must always be honoured.
- **Status:** current

### D-345 — Card Studio 2 follow-ups
- **Area:** security
- **Date:** 12 November
- **Decision:** Member card photo finalize strips EXIF (including GPS) and normalises orientation. Members can opt out of background removal behind a space notice (the notice version is stored with each request, and staff and bulk requests skip opted-out members). Code 39, EAN-13/UPC-A, PDF417, Data Matrix and Aztec join Code 128 and QR with browser/server parity fixtures, and CSV merge preview uses the published version.
- **Why:** Remove location metadata from photos and respect opt-out.
- **Status:** current
- **Implemented in:** `backend/apps/card_designs/`

### D-338 — GitHub profile badge rule
- **Area:** security
- **Date:** 11 November
- **Decision:** A profile shows the GitHub contribution calendar and badge only when the owner has a linked GitHub sign-in matching the username; otherwise the username is a plain unverified link. New 0.12.0 reports honour Machine Manager scope.
- **Why:** Prevent claiming someone else's GitHub identity.
- **Status:** current

### D-336 — Security review fixes
- **Area:** security
- **Date:** 11 November
- **Decision:** A minor's global profile is visible only to members of the minor's own spaces, and open-web consent needs guardian consent. Non-co-members see only name, handle, avatar and sections marked public. A deployment-wide DRF default throttle plus scoped throttles cover profile lookups, handle checks, display claim, Anthias test, adapter and watch routes. Handle checks never reveal whether an email exists. Anthias private-LAN targets are allowed by default on self-host and off on managed, adapter-reported minutes are clamped to real elapsed time, adapter staff routes check machine scope, PIN brute force has per-device and per-space budgets with a uniform denial reason, and machine access grants are scoped to a makerspace.
- **Why:** Close the High to Low findings of the pre-release security review.
- **Status:** current

### D-335 — Calls from the security findings review
- **Area:** security
- **Date:** 11 November
- **Decision:** The machines access-grant conversion keeps access for a member who met the requirements of any purpose the machine was gated for, and gives the Space Manager a list of converted grants to review. Platform limit defaults keep the last known value on lookup failure and never fall back to unlimited. The merged global profile migrates with public visibility off unless every legacy profile had public consent. The display polling credential moves from the URL path to an Authorization header.
- **Why:** Nobody should lose access on upgrade, and failures must never widen exposure.
- **Status:** current

### D-308 — Every account needs a username
- **Area:** security
- **Date:** 11 November
- **Decision:** Every account must have a handle. All sign-up methods ask for a username with live availability checking and a pre-filled suggestion; existing accounts without one get a blocking "Choose your username" step on next sign-in, and API and native clients receive a typed `handle_required` flag. A migration auto-claims valid, free usernames, and machine API clients and kiosk tokens are unaffected.
- **Why:** Profiles are addressed by handle across the platform; supersedes the "no handle until chosen" rule of D-305.
- **Status:** current
- **Implemented in:** `backend/apps/accounts/authentication.py`, `backend/apps/accounts/schemas_auth.py`

### D-285 — Notification audit and Django admin at /control/
- **Area:** security
- **Date:** 11 November
- **Decision:** Notifications get an end-to-end audit (event, recipients, channels, template, translation, preferences, scoping). The Django admin at `/control/` is grouped by area, reaches every model once, shows immutable and append-only records read-only, never shows secrets, routes actions through services with audit, and uses the app's dark brand tokens; the React platform console uses the same groups and names.
- **Why:** Superadmin tools should be consistent and safe.
- **Status:** current

### D-240 — Platform credential fallback applies on every install
- **Area:** security
- **Date:** 10 Nov 2026
- **Decision:** Platform credential fallback (Wallet and other per-space integrations) applies on every install regardless of the hosting switch, as decided in D-223; the hosting switch never disables it for Own spaces.
- **Why:** The limits work had wrongly gated the wallet fallback on `hosts_other_spaces()`.
- **Status:** current

### D-237 — Backend image base: Debian trixie
- **Area:** security
- **Date:** 10 Nov 2026
- **Decision:** Ship Debian trixie (stable) with pip removed from the final image; remaining base-package findings keep per-CVE notes, and `DEBIAN_RELEASE=forky` stays an opt-in build option.
- **Why:** Cleared the Python findings; remaining findings not reachable from the app.
- **Status:** superseded by D-262
- **Implemented in:** backend/Dockerfile

### D-231 — Fix backend image OS CVEs rather than only document them
- **Area:** security
- **Date:** 10 Nov 2026
- **Decision:** Use the newest base with a build-time upgrade and purge every OS package not needed at runtime, with a runtime smoke test of each candidate (migrations, pg client 16, ffprobe, ONNX/PDF libraries, age, backup scripts). The image stays on a Debian-family base; an alternative minimal distro was dropped. Anything still unfixable keeps a per-CVE risk note.
- **Why:** The maintainer wanted reachable CVEs removed, not accepted.
- **Status:** partly superseded by D-262
- **Implemented in:** backend/Dockerfile

### D-229 — Guest pass immutability and deferred minor fixes
- **Area:** security
- **Date:** 10 Nov 2026
- **Decision:** Guest passes get a database trigger: no DELETE outside the immutable-delete purge scope, frozen identity/entitlement columns, and a closed pass never changes status (window, waiver and revoke fields stay writable). A pass ending while the space is closed is due at the last open-session close inside the window. House bookings send no requester mail, the venue panel drops payer identity, and a volunteer credit that fully covers a renewal records a zero-amount covered marker instead of a 0.01 debt.
- **Why:** Reason not recorded
- **Status:** current

### D-222 — Free Gilroy weights only; image CVE route
- **Area:** security
- **Date:** 9 Nov 2026
- **Decision:** Only the free Gilroy weights are used with Outfit and Unbounded; no commercial licence is purchased and the fallback, if ever required, is Outfit everywhere. The backend image replaces Debian's `ffmpeg` with a minimal `ffprobe` compiled from a pinned, checksum-verified FFmpeg source (mov/matroska demuxers, file/pipe protocols only, no libxml2), keeping one published image; the FFmpeg version is tracked in the SBOM. The live browser role/theme/viewport pass runs last.
- **Why:** Removes FFmpeg's Debian dependency tree including libxml2.
- **Status:** current
- **Implemented in:** backend/Dockerfile

### D-200b — Security and hosting audit outcomes
- **Area:** security
- **Date:** 6 Nov 2026
- **Decision:** Every archive schedule ends in a purge, so the slug is required for every schedule. Loopback `http://` OAuth redirect URIs stay allowed in production (native apps, RFC 8252); any other `http://` is refused. The SMTP peer check runs after TCP connect and before any byte is sent (before the handshake for implicit TLS). PNG/WebP uploads are capped at 16 MP and JPEG at 50 MP (decoded at the smallest DCT scale), with only the attach step throttled. The control-plane tunnel trusts only loopback, 10/8, 172.16/12, 192.168/16 and fc00::/7 (CGNAT stays untrusted) because `ipaddress.is_private` also covers documentation and reserved ranges.
- **Why:** Audit findings; the private-range defect was a real bug but not exploitable from routable space.
- **Status:** current
- **Implemented in:** backend/apps/apiclients/oauth_provider.py, backend/apps/outbound_policy.py

### D-197b — Superadmin controls: one audited bypass guard, paused spaces servable to the superadmin
- **Area:** security
- **Date:** 5 Nov 2026
- **Decision:** The superadmin write bypass is a single guard, audited once per space per request or job as `space_control.superadmin_bypass`; `/control/` writes are confirmed and audited too. Celery jobs carry the actor header and are re-checked on the worker, and scheduled sweeps get no bypass. The console confirmation asks once per space every 10 minutes; platform control routes never ask. A paused space is servable to the superadmin (reads normal, writes audited) through the servability layer; archived spaces stay unservable for everyone, "archive now" on a paused space ends the pause in the same transaction, and `/control/` and raw-SQL analytics are not admitted.
- **Why:** Reason not recorded
- **Status:** current
- **Implemented in:** backend/apps/space_controls/superadmin_bypass.py

### D-197d — API scopes: per-area public scopes, peer clients, platform accounts cannot hold tokens
- **Area:** security
- **Date:** 5 Nov 2026
- **Decision:** Area scopes `public:<area>:read|write` narrow `public:read/write`. Staff and member routes stay session-only for HMAC API clients. A `peer` client is tenant-bound to catalogue/events/stats GET only; a Space Manager may create server or peer clients, browser clients stay superadmin-only. Personal tokens and OAuth share one scope set (`account:*`, `public:*`, per-area, `staff:*` bound to one space). Platform/superadmin accounts cannot hold personal tokens or connect OAuth apps, because a leaked superadmin token would be platform-wide. OAuth lives under `/api/v1/oauth/` with an SPA consent page (consent needs MFA re-auth), code 60 s, access 1 h, refresh 30 d, 120 requests/min per credential.
- **Why:** A leaked superadmin token would be platform-wide; the superadmin keeps full access through the console and `/control/`.
- **Status:** current
- **Implemented in:** backend/apps/apiclients/oauth_provider.py, docs/api-client-protocol.md

### D-197g — Superadmin space-control lifecycle (suspension, pause, plans, invoices)
- **Area:** security
- **Date:** 5 Nov 2026
- **Decision:** Suspension is a lifecycle state with reasons in `SpaceControlState`. Read-only blocks every user's writes while delivery, expiry, retention, settlement, cleanup, exports, PII windows, unsubscribe and bounces keep running; paused spaces refuse all writes except settlement and the controls and hold queued messages. The superadmin may act in either state (audited, with a warning), scheduled steps run as the scheduling superadmin and are re-validated, and the paused reason is shown only to the superadmin. Archive reminders go at 7/1 days and purge reminders at 30/7/1 days. Plans need the switch AND managed mode (override beats plan beats deployment default); invoice numbers are `SWH-<year>-<5 digits>`; invoices and receipts outlive a purge.
- **Why:** Reason not recorded
- **Status:** current
- **Implemented in:** backend/apps/space_controls

### D-191 — Optional web route to the control plane
- **Area:** security
- **Date:** 5 November
- **Decision:** `CONTROL_PLANE_PROXY=true` (with an optional CIDR allowlist) keeps serving `/control/` on the site's own address; default stays false and existing installs keep their setting. The access middleware follows the setting, and docs keep both routes with server/SSH first.
- **Why:** The maintainer chose to keep the opt-in route.
- **Status:** current
- **Implemented in:** `backend/config/control_plane_access.py`, `scripts/control-plane-settings.sh`

### D-190a — Control-plane restructure
- **Area:** security
- **Date:** 5 Nov 2026
- **Decision:** Tunnel trust is a fixed header set only by the tunnel Caddy site, trusted only with `CONTROL_PLANE_TUNNEL=on` and a private/loopback peer; loopback counts as "server" only with no forwarding headers; with the proxy on the edge enforces the CIDR list. `/mfa/reauth/` is part of the control plane and console paths run the source gate where `/control/` does. The sidebar has 13 sections, dangerous unconfirmed actions share one generic confirmation page, and account lookup is by exact username with no PII returned. Self-host move export is a signed 5-minute single-use link; "run drill now" uses the newest restorable archive (409 if drills are not configured).
- **Why:** Reason not recorded
- **Status:** current
- **Implemented in:** backend/apps/space_controls, docs/INVARIANTS.md

### D-190b — Web forms for platform provider settings; host-only list
- **Area:** security
- **Date:** 6 Nov 2026
- **Decision:** Platform SMS/push/WhatsApp/attestation credentials are edited through the `/control/` forms with shared validation and encryption; secrets are write-only. Each provider has a check (SMS test send, push FCM sign-in and APNs key signature, WhatsApp Graph phone-number call; attestation is checked on save). Space Manager chat templates use `MANAGE_MAKERSPACE` with no re-auth. Still host-only: platform/server key rotation, platform re-encryption, the RLS sync, axes and OTP/OAuth grant plumbing rows, and member profiles/projects. Capability purge is not gated by the switch it purges.
- **Why:** The aim was that nothing a web form can safely do remains `/control/`-only (decision 190).
- **Status:** current
- **Implemented in:** backend/apps/space_controls, backend/apps/operations/cloud_jobs/task_sources.py

### D-189 — Control plane access (server-only default)
- **Area:** security
- **Date:** 5 November
- **Decision:** `/control/` is reachable by default only from the server itself (loopback or the 127.0.0.1 tunnel port via SSH), and a middleware refuses it elsewhere, so the public origin answers 404. Only superadmins ever reach it.
- **Why:** Reduce exposure of the most powerful surface.
- **Status:** partly superseded by D-191
- **Implemented in:** `backend/config/control_plane_access.py`, `scripts/control-plane-settings.sh`

### D-162 — Staff password sign-in when member passwords are off
- **Area:** security
- **Date:** 1 November
- **Decision:** With member password sign-in off, people holding a staff role still sign in with a password so staff are never locked out; it stays rate-limited, IP-blocked and MFA-protected. Staff-track authority is suppressed inside native member grants and claim sessions.
- **Why:** Staff lockout is worse than the accepted cost of a staff username being distinguishable before the password check.
- **Status:** current
- **Implemented in:** `backend/apps/accounts/rbac.py`

### D-157 — Staff sign-in security defaults
- **Area:** security
- **Date:** 1 November
- **Decision:** `security.passkeys_allowed` off is the stricter value (if any of a person's staff spaces disallows passkeys they must use the authenticator; a lock forces passkeys off). Staff session maximum defaults to 168 hours and idle timeout to 0 (off). Retention: alert labels cleared at expiry and rows deleted 30 days later, IP auto-block rows deleted 7 days after the block ends, passkey ceremonies deleted 1 day after expiry. IPv6 is compared per /64, IP auto-blocking defaults on, and the passkey relying-party name is "Space Works".
- **Why:** Fills gaps left by a lost login-security plan.
- **Status:** current
- **Implemented in:** `backend/apps/accounts/login_security_settings.py`

### D-135d — Sign-in grace and security defaults for staff (Q-A1 to Q-A4)
- **Area:** security
- **Date:** 29 October
- **Decision:** Existing unenrolled staff get a 3-day two-factor grace from first sign-in after the upgrade, once per person ever, Space Managers included. During the grace, security settings, PII windows, exports, credential resets and role changes still require 2FA. Members use platform defaults, and CAPTCHA configured on a space's domain applies to everyone signing in there.
- **Why:** Reason not recorded
- **Status:** current
- **Implemented in:** `backend/apps/accounts/mfa_grace.py`

### D-128a — Staff MFA grace and security settings
- **Area:** security
- **Date:** 28 October
- **Decision:** A person who gains a staff role without 2FA has a 3-day grace period with a banner, after which staff screens are blocked until they enrol; member features are never blocked. Per-space security settings take the strictest value across a person's staff spaces and include risk check, remembered-device days, staff session and idle limits, CAPTCHA mode, passkeys allowed and a staff IP allow-list, all lockable by the superadmin.
- **Why:** Reason not recorded.
- **Status:** current
- **Implemented in:** `backend/apps/accounts/login_risk.py`

### D-128d — Backup, key and restore follow-ups
- **Area:** security
- **Date:** 28 October
- **Decision:** Restored rows follow merged-into pointers to the survivor, and staff logins travel with a space moved to another server (a Space Manager requests, the superadmin runs it). Drills read the live key in memory only with a throwaway database, backup emails to spaces are dropped in favour of an optional notice to the platform email, row-level security is report-only with a warning on owner-role installs, and re-key creates a new key now with background re-encryption.
- **Why:** Reason not recorded.
- **Status:** current

### D-123 — Spreadsheet import parsed on the server
- **Area:** security
- **Date:** 28 October
- **Decision:** The client-side spreadsheet library is removed because of unpatched alerts. Bulk Import uploads the file to an rbac-scoped, audited, documented staff endpoint that parses it with openpyxl using read-only, no-formula and size/row limits, keeping the preview and confirm flow. Email sending uses plain django-anymail with cryptography at version 50 or newer.
- **Why:** There was no patched release of the browser library.
- **Status:** current

### D-120 — Per-space keys and row-level security
- **Area:** security
- **Date:** 27 October
- **Decision:** Per-space encryption keys get rotation and emergency re-key from the control plane (re-auth, audited, visible to the space's managers), a per-space search key, and a Postgres row-level-security backstop. The idea of a sovereign lock-out key broker is dropped: the platform key always works.
- **Why:** The always-on superadmin decision makes lock-out keys meaningless.
- **Status:** current
- **Implemented in:** `backend/apps/tenant_rls`, `backend/apps/encryption`

### D-114 — PII masking for the superadmin
- **Area:** security
- **Date:** 27 October
- **Decision:** Staff names and emails are masked for the superadmin until a PII window is open, and an account in no space stays masked with its reveal audited at platform level. Platform email logs with no space are unmasked, logs belonging to a space stay masked, and the control-plane request review page stays unmasked as a decision surface.
- **Why:** Reason not recorded.
- **Status:** current

### D-113 — Per-space restore never changes other spaces
- **Area:** security
- **Date:** 26 October
- **Decision:** In a per-space restore other spaces are never changed: their rows pointing into the restored space are kept and re-linked to restored rows where they exist, and are listed in the preview. A row that would be left dangling blocks the restore until resolved.
- **Why:** Detaching rows would change other tenants' data.
- **Status:** current

### D-111 — Per-space backup and restore rules
- **Area:** security
- **Date:** 26 October
- **Decision:** Backup and restore is one flow for both scopes (whole platform or one space) in the web panel and the control plane: restore points, back up now, preview, confirm with re-auth, live progress. Per-space archives are encrypted to the platform key and the server identity, a nightly archive is made per live space, a mandatory safety backup precedes every restore, and the live audit history, later payments and later evidence are kept. Security locks only tighten, a PII reveal is a 30-minute per-space window with a reason, and the Space Manager role is not delegable for security settings.
- **Why:** Reason not recorded.
- **Status:** current
- **Implemented in:** `backend/apps/backup/admin_space_backup.py`, `docs/backup-and-restore.md`

### D-110 — The superadmin is always on
- **Area:** security
- **Date:** 26 October
- **Decision:** The per-space superadmin off switch and all hidden-space behaviour are removed, as are archive recipients and custody; the platform key always unlocks every space's backup. Each space has its own security settings editable by the Space Manager and the superadmin, who can lock a setting so the space cannot loosen it. The superadmin can back up and restore a single space from the control plane. Viewing members' encrypted PII asks for a reason and recent re-auth and writes an audit row the space's managers can see. Only the superadmin manages Space Managers.
- **Why:** Reason not recorded.
- **Status:** current
- **Implemented in:** `backend/apps/backup/admin_space_backup.py`, `backend/apps/space_controls`, `backend/apps/encryption`

### D-104 — Member accounts default on
- **Area:** security
- **Date:** 25 October
- **Decision:** New makerspaces start with member accounts on, and a space can deliberately switch to account-less. Staff-registered walk-ins keep their own person record and claim session, the workshop profile stays account-less, and account-less borrowers can self-checkout kits after the email code with unchanged evidence rules.
- **Why:** Reason not recorded.
- **Status:** current

### D-91 — Account-less requests and self-checkout
- **Area:** security
- **Date:** 24 October
- **Decision:** In a space without member accounts everyone requests through the name, phone, email and email-code form, even if signed in, and self-checkout (with unchanged evidence rules) is also allowed without an account. The membership module requires member accounts, which dependency completion adds automatically. Room-scoped booking alerts reach roles under the same rule as named people.
- **Why:** Reason not recorded.
- **Status:** current

### D-80 — Account-less spaces use verified contact details
- **Area:** security
- **Date:** 22 October
- **Decision:** Accounts are global, one per person. A space without the member-accounts module has accounts for staff only; public borrowers give name, phone and email (all required) and confirm the email with a one-time code before the request is accepted. The typed name is shown where borrower names are public, while phone and email are staff-only and encrypted. A space with member accounts requires a signed-in account.
- **Why:** The code stops someone using another person's address.
- **Status:** current

### D-74 — Passkeys, imports and plan scope
- **Area:** security
- **Date:** 22 October
- **Decision:** Passkeys are offered but never forced (staff may use one instead of TOTP). Member import is CSV first, with Google Sheets as a later follow-up.
- **Why:** Reason not recorded.
- **Status:** current

### D-66 — MFA rollout and reset authority
- **Area:** security
- **Date:** 21 October
- **Decision:** Defaults: no automatic community membership for converted staff, superadmin-only alerts, breached-password check on with a 2 s fail-open timeout, web-only passkeys, no merge deadline, and member device grants revoked at cutover. The superadmin can always reset MFA, and a Space Manager only when all of the person's elevated authority is in that space and they are not a Space Manager.
- **Why:** Reason not recorded.
- **Status:** partly superseded by D-128a

### D-65 — Account merge needs proof
- **Area:** security
- **Date:** 21 October
- **Decision:** Nothing merges on email alone. Existing staff accounts convert to normal accounts keeping their roles; a merge into a member account happens only after the person signs into the member account and proves the staff account (password and authenticator code) or both addresses pass a fresh emailed code.
- **Why:** Email matching alone could let someone claim another person's account.
- **Status:** current

### D-62 — Login security
- **Area:** security
- **Date:** 21 October
- **Decision:** Staff must use an authenticator (TOTP) in every space, with passkeys offered but never forced, and staff signing in through a provider still enter the code. Added controls are an unusual-login check, login alert emails with a "this wasn't me" sign-out-all link, automatic blocking for credential stuffing with a superadmin block/allow list, a fail-open breached-password check, and an optional CAPTCHA after failures. The superadmin keeps username and password plus the existing control-plane step-up.
- **Why:** Reason not recorded.
- **Status:** current
- **Implemented in:** `backend/apps/accounts/login_risk.py`, `backend/apps/accounts/admin_mfa_reset.py`
