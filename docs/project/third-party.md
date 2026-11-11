---
title: Third-party software and fonts
group: Project
order: 20
summary: The fonts and notable dependencies Space Works ships with, and the licence each one carries.
---

# Third-party software and fonts

Space Works itself is AGPL-3.0-or-later ([License](license.md)). It builds on a large amount of other
open-source software, and a few files in the repository are under other terms. The repository's `NOTICE` file
is the authoritative list; this page summarises it.

## Fonts

The self-hosted fonts are **not** covered by the AGPL. The repository ships only redistributable faces.

| Font | Used for | Licence |
| --- | --- | --- |
| Outfit (variable, weights 100 to 900) | The primary text face: body, interface, labels | SIL Open Font License 1.1 |
| Unbounded (variable, weights 500 to 600) | One short accent phrase per layout | SIL Open Font License 1.1 |
| Gilroy ExtraBold (800) | Headings and display moments | Radomir Tinkov Free Font EULA |
| Gilroy Light (300) | Large light display text only | Radomir Tinkov Free Font EULA |

The licence texts are in `frontend/public/fonts/LICENSES/` and `backend/apps/events/certificates/fonts/`.

### The Gilroy free font EULA, stated factually

The EULA (version of 1 January 2016) grants a perpetual, worldwide, non-exclusive, non-transferable licence.

It allows you to:

- download, install and use the font for personal and commercial purposes, on unlimited devices;
- use it in fixed-size graphics, printed matter and scalable drawings;
- generate web font formats and use them on websites through `@font-face`;
- embed the font into software or hardware products used by their purchasers.

It forbids:

- modifying the font or creating derivative works without written consent, so the files are shipped
  unmodified;
- distributing, selling, renting, leasing, assigning, adapting or otherwise making the font available to any
  third party.

The last restriction sits in tension with publishing the raw font files in a public repository and in
self-hostable release artefacts, while the embedding and `@font-face` permissions allow serving them from a
website. The EULA does not resolve that tension, and the Gilroy files are not covered by the AGPL. Anyone who
redistributes Space Works should obtain or accept the Gilroy licence themselves. If you prefer to avoid the
question, delete the two `Gilroy-*.woff2` files and the other Gilroy copies named in
`frontend/public/fonts/README.md`; every font stack falls back to Outfit.

The font choices are also described in that README, with the full EULA text alongside it.

## Notable dependencies

Space Works depends on many npm (frontend) and pip (backend) packages, each under its own licence. The
complete lists are in `frontend/package.json` and `backend/requirements.txt`. The following are called out in
`NOTICE` because their licence is worth knowing about:

| Component | Where | Licence |
| --- | --- | --- |
| pillow-heif (decodes HEIC and HEIF uploads) | Backend image | BSD-3-Clause; its wheels bundle libheif and libde265 (LGPL-3.0) and x265 (GPL-2.0-or-later). Licence texts ship inside the installed package. |
| pypdfium2 (rasterises ID cards) | Backend | Apache-2.0 or BSD-3-Clause, bundling PDFium (BSD-3-Clause) |
| onnxruntime and the u2netp model (card photo background removal) | Backend | MIT and Apache-2.0. An operator fetches the model with `manage.py fetch_card_photo_model`. |
| Fonts for cards beyond the bundled ones | Fetched on demand from the Google Fonts catalogue | Each family keeps its own licence (SIL OFL 1.1, Apache-2.0 or the Ubuntu Font Licence) |
| webauthn (py_webauthn), pyOpenSSL, pyasn1, tldextract and others | Backend, for passkeys | BSD, Apache-2.0, MIT and MPL-2.0 (the bundled Public Suffix List snapshot, data only) |
| @simplewebauthn/browser | Frontend, for passkeys | MIT |
| Lingui | Frontend, translation pipeline | MIT |
| GNU gettext | Backend image build only | GPL-3.0-or-later; a build tool that does not ship in the final image |
| three, fflate, linkedom, @tracespace/core | Frontend, maker-file previews | MIT and ISC |
| occt-import-js (OpenCascade) | Frontend, 3D previews | LGPL-2.1, loaded as a separate WebAssembly module |
| Silo (`pgsty/silo`) | Bundled object storage | AGPL-3.0, a maintained fork of MinIO |
| FFmpeg `ffprobe` | Backend image | Built from a pinned FFmpeg source release with almost every component disabled |

## Adapted code and artwork

- The light and dark theme transition and the 404 page's pet behaviour are adapted from the open-source
  project **yuyu** by twilighty-abhi, which is AGPL-3.0.
- The mascot, Patch the painted wolf, is Space Works' own artwork, taken from the SpaceWorks-Design repository.

## Services you may connect

Space Works can call outside services only when you switch them on: mail providers, SMS and WhatsApp,
payment gateways, Cloudflare Turnstile, and sign-in providers. Those services have their own terms. Two
default-on behaviours do reach out: the breached-password check (a range query to the Have I Been Pwned API,
with a short timeout that fails open) and card font downloads from Google Fonts. On an offline server, set
`PASSWORD_BREACH_CHECK_ENABLED=False` and `CARD_FONT_DOWNLOADS_ENABLED=False`.
