---
title: The public profile
group: How-to guides
order: 230
summary: Your always-on public account card, published projects and public-space memberships.
---

# The public profile

Every account with a handle has one public profile at `/@<handle>`, for example `/@ada`. Anyone can open it without signing in. The old `/ada` address continues to work. There is no switch to take the profile offline.

## What visitors see

The public card shows your display name, avatar, bio and projects you chose to publish. It also lists each public space where you are an active member, with your role title and membership start date. Private or directory-hidden spaces, paused or archived spaces and revoked memberships are omitted, including when you view your own public page.

Minors and restricted or suspended accounts show **only their display name and avatar**. Their bio, projects and memberships are absent.

Contact details, internal account or row identifiers, loans, payments, evidence and audit records never appear.

## Edit your card

1. Open **Account**, then **Profile**.
2. Under **Public profile**, choose or check your handle. Select **View public profile** to open the public card.
3. Upload an avatar and edit your bio. **Show my bio** controls the bio section.
4. Add projects and choose which ones to show. The projects section switch also controls their publication. Project links must use HTTPS.
5. Save your changes. Memberships update from your active membership records; they have no publication switch.

Your account editor can hold richer profile information for authenticated features. Those fields are not added to the public card. A space's member directory remains a separate, scoped surface.

## Existing data and operators

Existing profile content, projects and historical visibility/consent values are kept. The old visibility values do not hide the public card and are no longer editable through profile APIs or the UI. No data migration is required.

The public card is an account feature and works without a membership or enabled tenant module. A membership is listed only when that space's public site and membership module are enabled; turning either off hides the listing without deleting data. Restoring them restores eligible listings. Host and browser-origin tenant fences and public request limits still apply; responses use `Cache-Control: no-store` so privacy changes take effect on the next read.

Profiles remain account-owned, outside per-space PII encryption and tenant dumps. Contact and guardian details retain their existing private storage rules. A public profile grants no staff or tenant permissions.

## See also

- [Usernames](usernames.md)
- [Memberships](../modules/memberships.md)
- [Let people check in by location](presence-check-in.md)
