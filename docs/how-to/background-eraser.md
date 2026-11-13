---
title: Remove card photo backgrounds
group: How-to guides
order: 131
summary: Connect your own background-removal service, switch the feature on, and use it on card photos one by one or in a bulk upload.
---

# Remove card photo backgrounds

Card designs can show a holder cut out of their photo's background. SpaceWorks does this through a **background
eraser service that you run**: any HTTPS service that implements the [Image Adapter API](../image-adapters/README.md).
SpaceWorks does not ship a service or use a third-party cloud by default; photos go only to the address you enter.

## Before you start

1. **A provider.** Build or host one that implements the contract. The [Build an image provider](../image-adapters/build-a-provider.md)
   page has a minimal pseudo-implementation, a test script and a conformance checklist. Choose a shared secret of at
   least 16 characters.
2. **The switch.** Turn on **Card photo background eraser** (`cards.photo_cutout`, off by default) for the space in
   **Settings › Features**. It needs the Membership module; event cards also need event ID cards, and staff cards need
   staff ID cards. Off means no button, no menu item and a 404 from the API; stored cut-outs are kept.

## Connect the provider

- **One for the whole server** (superadmin): **Platform settings › Integrations & analytics › Background eraser**.
  Enter the address and the secret. A private address such as `http://bg-eraser:8080` is fine here.
- **One for a single space** (Space Manager): **Settings › Background eraser**. The address must be public `https`.
  A space's own service wins over the platform's; untick *Use the platform's service* to stop a space falling back to it.

Press **Test connection**: SpaceWorks sends a signed health check and tells you in words what is wrong (wrong secret,
unreachable, wrong contract version). The secret is never shown again after saving; only a short fingerprint is.

## Use it

- **One photo (staff).** Open a member, staff or event card's photo dialog and press **Remove background**. It needs
  the same authority as uploading that card's photo. A queued job shows *Removing the background…*, then the result on a
  checkerboard. Choose **Use cut-out** or **Use original** at any time, **Run again**, or **Discard cut-out**.
- **Your own photo (members).** On **My cards**, under the photo, a member ticks that the photo is sent to the eraser
  service and presses **Remove background**. Nothing is sent without the tick.
- **Many photos.** From **Member cards** (menu **All cards › Upload many photos…**), **Staff cards**, or an event's
  cards, choose photos or a zip. Files are matched to cards by name: the card number first (`TNK-0042.jpg`), then the
  part of the email before the `@`, then the full name (case, spaces, dashes, underscores and accents do not matter,
  and `Raman Priya` matches `Priya Raman`). Review the table: matched photos, ambiguous names (pick one), unmatched
  files (pick a person or skip) and holders who already have a photo (keep or replace). Tick *Remove backgrounds after
  upload* (shown only when a service is set up) to queue a removal for each attached photo, then **Apply**.

The original is never changed or deleted by a cut-out. Staff ID cards show the member card's photo, so their cut-out
belongs to that photo.

## The notice and opting out

While the eraser can run in a space, members see this notice on their card photo (**My cards**) and on the space's
privacy page: *card photos may be sent to this space's background-removal service, which cuts the person out of the
background; the original is always kept; you can opt out.* A member who ticks **Never send my photo to the
background-removal service**:

- has any existing cut-out deleted, and their card prints the original photo;
- is skipped by staff (**Remove background** answers that the member opted out) and by bulk uploads (the photo is still
  attached; the row says the member opted out);
- can untick it at any time to allow removal again.

The notice has a version (`2026-11-12`); every background-removal request stores the version in force, and opting in
or out is in the audit log. The choice is kept with the card that owns the photo (a staff ID card follows its member
card), moves with the space to another server, appears in the member's own data export, and is removed with the card.

## Show the cut-out on the card

In the Card Studio, select the **Photo** layer and choose its **Photo version**:

| Photo version | What prints |
|---|---|
| Original photo | The original, in the frame's shape (square, rounded, circle or arch) |
| Cut-out (background removed) | The cut-out whenever one is ready for the holder's current photo; otherwise the original |
| Each holder's choice | The cut-out only for holders who chose **Use cut-out**; everyone else the original |

The cut-out is drawn without the frame's mask (its own transparent edge is the shape), over whatever is behind it: a
colour, a gradient, an uploaded background or template artwork. The frame's **zoom** and **focal point** crop it the same
way as the original, and the **sticker outline** and **shadow** follow its edge. With no service, the switch off, no
cut-out yet or a stale one, the original prints: a card is never blank. **Preview as** a real holder shows their real
cut-out in the designer; the sample people show a silhouette.

## Limits

| What | Limit |
|---|---|
| Photos per bulk upload | 500; each at most 8 MB |
| A zip | 200 MB, at most 2000 entries and 600 MB unpacked; no zips inside zips, no passwords |
| Background removals per month | The limit `photo_cutout_jobs_monthly` (none unless the platform operator sets one), counted from the audit log, so a re-run or a discarded cut-out still counts. At the limit new jobs wait until next month; existing cut-outs keep working. A bulk upload still attaches every photo and marks the rows whose removal was refused |
| Retry | A busy or unreachable service is retried 4 times in total (30 s, 2 min, 10 min) |

The bundled nginx configs (`frontend/nginx.conf`, `deploy/nginx.api-only.conf`) allow up to 220 MB for the
bulk-photo route only (`/api/v1/admin/makerspaces/<id>/card-photo-batches/<id>/files`); every other API route keeps its
smaller limit. The bundled Caddyfiles set no body limit. The web app sends photos in requests of at most 20 files and
24 MB (a zip goes alone). If you put your own proxy in front, allow at least 25 MB on that route, or 220 MB to accept
a full-size zip. Django needs no change: uploaded files are streamed to disk and are not counted by
`DATA_UPLOAD_MAX_MEMORY_SIZE`.

## Privacy and retention

- Photos are personal data, and every uploaded card photo is re-encoded by the server: the camera's orientation is
  applied, then EXIF and other metadata (GPS location, device, timestamps) are removed, and the long edge is capped at
  1200 px. A member-card photo can be up to 8 MB; a larger file is refused before it is uploaded.
- The holder (or staff on their behalf) consents to the photo being stored and printed;
  bulk upload requires staff to confirm that for everyone in the batch, and a member consents separately to the photo
  being sent to the eraser service.
- Photos for a bulk upload wait in private storage while you review and are deleted when you apply or cancel, or after
  7 days.
- A cut-out is a private derived copy. It is deleted with its original photo, when you discard it, and when the card,
  account or space is deleted. A replaced photo makes the old cut-out stale: it is never printed, and it is deleted
  (and its storage given back) as soon as the new photo is saved.
- Cut-outs and bulk batches are not part of a data export or a space move; the original photos are, and a cut-out can
  be made again.
- Every request, result, choice, discard and bulk batch is in the audit log by id and code, never with a name or photo.
  Provider addresses and secrets are never in an audit row.
