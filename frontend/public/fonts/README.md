# Font files

Owner decision (9 November 2026): this repository is AGPL, so it ships **only** redistributable
faces. The commercial Gilroy Regular/Medium/SemiBold/Bold files were removed from the repository
(frontend, member offline page and backend print faces).

| File | Role | Licence |
|---|---|---|
| `Gilroy-ExtraBold.woff2` (800) | headings and display brand moments | Radomir Tinkov Free Font EULA, `LICENSES/Gilroy-Free-Font-EULA.txt` |
| `Gilroy-Light.woff2` (300) | large light display text only, where the spec calls for Light | same EULA |
| `Outfit-Variable.woff2` (wght 100–900) | primary text face: body, UI, labels, emphasis at 400–700 | SIL OFL 1.1, `LICENSES/OFL-Outfit.txt` |
| `Unbounded-Variable.woff2` (500–600) | one short accent phrase per layout | SIL OFL 1.1, `LICENSES/OFL-Unbounded.txt` |

The Gilroy and Outfit files are byte-for-byte copies from the SpaceWorks-Design repository (`fonts/`).
There is no monospace face: machine strings use Outfit with tabular numerals (`.code-text`); Outfit has
no `zero` feature, so `slashed-zero` is a no-op.

`src/index.css` declares the faces with `font-display: swap`, and `body` sets `font-synthesis: none`, so a
`Gilroy` request at an undeclared weight snaps to the nearest real face (≤500 → Light, ≥600 → ExtraBold)
instead of being faked. `index.html` preloads Outfit and Gilroy ExtraBold.

## What the Gilroy free EULA allows (read before redistributing)

The EULA (version 1 January 2016, copied verbatim in `LICENSES/`) grants a perpetual, worldwide,
non-exclusive, **non-transferable** licence to:

- download, install and use the font for personal **and commercial** purposes (a), on unlimited devices (g);
- use it in fixed-size graphics, printed matter, EPS/scalable drawings (b, c);
- **generate web font formats and use them on websites via `@font-face`** (h);
- **embed the font into software or hardware** products used by their purchasers (d, i).

It forbids:

- modifying the font or creating derivative works without written consent (e) — so these files are
  shipped unmodified (no subsetting, no outline conversion);
- **distributing, selling, renting, leasing, assigning, adapting or otherwise making the font available
  to any third party** (f).

**Risk:** clause (f) conflicts with publishing the raw font files in a public source repository and in
self-hostable release artefacts, while clauses (d), (h) and (i) permit embedding in software and serving
via `@font-face`. The EULA does not resolve that tension. The files are shipped on the owner's decision;
they are **not** covered by the AGPL (see `NOTICE`), and downstream redistributors must obtain or accept
the Gilroy licence themselves. If written permission from Radomir Tinkov is not obtained, the safe
fallback is to delete both `Gilroy-*.woff2` files — every stack falls back to Outfit — plus the
ExtraBold copies in `public/member-pwa/offline.html` (inline `data:` URI, so the offline page works
without the network) and `backend/apps/events/certificates/fonts/Gilroy-ExtraBold.otf` (share-card title).
