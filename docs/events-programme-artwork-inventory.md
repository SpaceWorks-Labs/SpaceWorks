# Events programme ARTWORK inventory and handoff

Branch `lane/events-artwork`, baseline `72bf7be75ceeb5a8b463008757086548fb566077`.
Owned implementation only; no staging, commits, migrations, merges or pushes.
The pre-existing untracked `frontend/src/test/staffActor.ts` is untouched.

## Built per approved plan

| Plan | Delivered |
| --- | --- |
| §1 decisions 31–32 / §10 delight / §15 ARTWORK | Exactly **70 original themed SVGs**, 35 reviewed light/dark pairs: 58 frontend + 12 packaged template backgrounds |
| §9 / §10 gaps 1–3 / frozen E seed v2 | Foundry, Contour, Blueprint certificates: three families, six themed revisions; Classic, Bold, Minimal badges: three families, six themed designs, each with six named-stock geometries |
| §9A / decision 33 | Typed selected-member-photo, logo and QR slots; explicit placeholder fallback, no embedded profile choice, member identity or live credential |
| §13 / §15 / §16.10, .15, .17 | Theme/semantic/consumer manifest, decorative/meaningful image props, safe-SVG and inventory tests, schema fixtures, local physical-size PDF/visual proofs |

## Source and construction

Read-only sources: `docs/brand/space-works-brand-guidelines-v1.pdf` v1.0
(17 pages; identity, logo, colour, typography and graphic-system rules),
`docs/brand/README.md`, original symbol/reversed symbol and lockup masters.
The approved 2026-10-15 font kit supersedes older type recommendations.
Research supplies interaction ideas only. No third-party assets, code,
palette, illustration, character, layout, text or font is included.

Original constructions use open flaps, print layers, perforations, workshop
notebooks, equipment boxes and a nozzle robot. The logo itself is never redrawn,
stretched or recoloured. Defaults use the complete appropriate supplied symbol
through a separate logo resource. All small illustrated flap motifs are ornaments.

Frontend SVG image documents cannot inherit their parent's CSS variables. Both
manifests therefore resolve the existing light/dark `index.css` tokens explicitly;
Vitest checks every value against that source. Print artwork uses the same values.
Dark artwork is separately drawn/coloured, with no inversion, transparency-based
text, filters, gradients or external fetches. Decorative accent fills never supply
unlabelled application status. Text remains live in consumer components or typed
template layers: Gilroy 400–700, one Unbounded 500–600 accent per layout.

## Exact SVG inventory

Every base below has `.light.svg` and `.dark.svg`. `I` means
`frontend/src/assets/illustrations`; `T` means
`backend/apps/events/default_templates`. The manifest is the authoritative
enumeration of all paths, dimensions, semantic role, alt/empty copy and consumer ID.

| Base under I | Pair count | ViewBox | Consumer IDs / owner |
| --- | ---: | --- | --- |
| `moods/{welcome,success,waiting,empty,error}` | 5 | 96×96 | `delight.mood.<name>` / P |
| `brand-loader` | 1 | 160×160 | `delight.loader` / P, G |
| `equipment-tag-404` | 1 | 320×240 | `delight.not-found` / P |
| `companion/{idle,walk,nap,print}` | 4 | 160×176 | `delight.companion.<pose>` / P |
| `empty/{applications,teams}` | 2 | 240×200 | `events.empty.<area>` / A |
| `empty/submissions` | 1 | 240×200 | `events.empty.submissions` / B |
| `empty/{judging,gallery}` | 2 | 240×200 | `events.empty.<area>` / D |
| `empty/{mentoring,volunteering}` | 2 | 240×200 | `events.empty.<area>` / C |
| `empty/certificates` | 1 | 240×200 | `events.empty.certificates` / E |
| `empty/{broadcasts,analytics,readiness}` | 3 | 240×200 | `events.empty.<area>` / F |
| `empty/saved-details` | 1 | 240×200 | `events.empty.saved-details` / P |
| `landing/workshop-demo` | 1 | 640×360 | `landing.workshop-demo` / P |
| `roles/hackathon` | 1 | 240×200 | `events.role.hackathon` / A |
| `roles/{volunteer,mentor}` | 2 | 240×200 | `events.role.<role>` / C |
| `roles/judge` | 1 | 240×200 | `events.role.judge` / D |
| `live-pass` | 1 | 360×180 | `events.live-pass` / E, P |
| **Frontend subtotal** | **29** | **58 files** | No missing/unregistered twin |

| Base under T/artwork | Pair count | Geometry / theme support |
| --- | ---: | --- |
| `certificate-{foundry,contour,blueprint}` | 3 | 297×210 mm, light/dark |
| `badge-{classic,bold,minimal}` | 3 | 100×100 ornamental coordinate canvas; fitted to each of the six stock documents, light/dark |
| **Packaged subtotal** | **6** | **12 files** |
| **Programme total** | **35** | **70 files** |

Badge backgrounds contain only scalable ornamental geometry. Only that background
image fills the stock; logos and QR are fitted without distortion, and photos use
the E renderer's consented bounded resource. Do not stretch a complete template
document to another stock. Select its already-defined document instead.

| Badge stock | Width × height (mm) |
| --- | --- |
| `a6-portrait` | 105 × 148 |
| `4x6` | 101.6 × 152.4 |
| `3x4` | 76.2 × 101.6 |
| `4x3` | 101.6 × 76.2 |
| `cr80-portrait` | 53.98 × 85.6 |
| `cr80-landscape` | 85.6 × 53.98 |

## Files and consumption API

- `I/{index.ts,manifest.ts,README.md}`: `getIllustration(id, theme)` and
  `illustrationImageProps(id, theme, decorative=true)` select exactly one twin.
  The latter uses empty alt + aria-hidden beside equivalent text, or the manifest
  alt for meaningful use. No React component, animation, page route or motion flag
  is installed by this asset package.
- `T/{__init__.py,manifest.py}`: explicit exports, twelve SHA-256 artwork entries,
  seed IDs/version/themes, palette and stock support; no framework/storage imports.
- `T/certificate_seeds.py`: `certificate_seed(family, theme)`, six
  `CERTIFICATE_SEEDS`; every seed includes all five approved text merge tags,
  typed logo, certificate ID and certificate-verification QR.
- `T/badge_seeds.py`: `badge_seed(family, theme, stock)`, six default
  `BADGE_SEEDS`, `iter_badge_stock_seeds()` yielding 36 render candidates.
  Every candidate has typed photo/logo/event-credential QR and placeholder fallback.
- `T/schema_fixtures.json`: all 42 literal documents, checksum-bound resources,
  dummy names and render requirements; points at G's frozen schema, never edits it.
- `backend/tests/events/programme/default_templates/test_inventory.py` and
  `I/__tests__/inventory.test.ts`: the focused inventory/contract checks.

E validates every document/resource before copy. G installs through E's owned
revision workflow, idempotent by `(seed_id, seed_version, theme)`; badge stock is
a render setting of one design, not 36 independently installed designs. Never
overwrite an edited template or issuance snapshot. No import-time DB writes.
Default previews are E's server API, not a browser seed registry. Copy resources
to owned immutable artwork; packaged source is deployment code and is never
removed by an event/tenant purge.

Minimum QR box is 21 mm (actual smallest 23.211 mm); QR resource includes at least
four modules of quiet zone and fits square without cropping. Default symbol is
at least 12 mm high; renderer preserves its full master and H/4 clear space.
Text boxes do not intersect, shrink-to-fit stays ≥6 pt, and backgrounds keep
ornaments out of text/identity/QR boxes. No synthetic italic is requested.

## Model manifest and routes

**No ORM models, fields, FKs, User edges, tenant object keys, migrations, runtime
routes or OpenAPI operations.** No state-changing workflow or audit write is added.
Packaged resource UUIDs are deterministic catalogue identities, not tenant PKs.
All logo/photo/QR placeholders are closed typed slots; resources contain only
relative packaged paths plus checksums, never URLs, DOB, contact tags or secrets.

## Verification and visual evidence

Local checks: all five Python files compile; standalone checks pass for 70 safe
SVGs/35 twins, twelve hashes, frozen layer keys/tags, 42 disjoint in-bounds layouts,
six stocks, source ceilings, exact fixtures and CLAUDE/AGENTS equality.
`npx tsc -b` passes. Focused Vitest passes **one file / six tests**, including
both inventories, token parity, safe markup/resources and decorative/meaningful axe.
No Docker, Django or pytest was run. Backend schema tests remain for G's runner.

Proof evidence lives in the session `scratchpad/ev/artwork/` directory:
`contact-sheet-{intended,small}.png`, `proof-sheet-{certificates,classic,bold,minimal}.png`,
42 named PDF files, 78 rasterized pages and `render-inventory.json` with exact
file hashes, physical size/page counts, fitted fonts and sizes. These are local
proofs, not shipped assets. `prepare_proof.py`, `proof.py`, `proof_sheets.py` and
`check.py` retain the reproducible proof/check logic there.

Proofs use ReportLab, the actual approved WOFF2 font outlines converted locally
to TTF (including Unbounded 500/600 instances), long accented sample names, the
unaltered symbol/reversed master, a dummy portrait and the no-photo alternative.
Poppler renders were visually reviewed at intended/half scale and all stock/theme
combinations. Physical PDF MediaBoxes were checked within 0.01 mm; all 78 pages
retain sample name text, fit at ≥6 pt and use high-contrast theme ink. Two ornament
overlaps found in initial review were corrected and the complete set regenerated.
These dummy QR slots deliberately say SAMPLE and contain no scannable encoding.

This is **local geometry/artwork acceptance only**, not a claim of E server-render
parity, valid QR encoding, browser-level consumer AA or final owner approval.
Chromium spawning is blocked (`spawn UNKNOWN`); bundled ReportLab/Poppler supplied
the local proofs. Separate `codex doctor` fails configuration/home resolution and
required endpoint reachability; no independent CLI review pass is claimed.

## CROSS-LANE needs and signatures

| Owner / integration point | Exact consumer files or packages; required evidence |
| --- | --- |
| A / step 4 | `frontend/src/features/{events,staff}/hackathonAdmission/**`: import applications/teams empty IDs and hackathon role ID; sign actual light/dark empty screens |
| B / step 4 | `frontend/src/features/events/hackathonSubmissions/**`: import submissions empty ID |
| C / step 4 | `frontend/src/features/events/contributions/**`, `frontend/src/features/staff/mentorDesk/**`: mentoring/volunteering empties and volunteer/mentor roles |
| D / step 4 | `frontend/src/features/events/hackathonGallery/**`, `frontend/src/features/staff/hackathonJudging/**`: gallery/judging empties and judge role |
| E / steps 4–5 | `backend/apps/events/{certificates,credentials,profile_photos}/**`, `certificate_templates.py`, `certificate_rendering.py`, `badge_templates.py`, `badge_rendering.py`: validate/copy seeds, real approved fonts, resource fit/quiet zone, authoritative 6/36 PDF inventory and selected/no-photo tests |
| E / step 4 | `frontend/src/features/staff/eventCredentials/**`, `frontend/src/features/events/eventPresentation/**`, `MemberEventTicketPage.tsx`: certificates empty and live-pass art; server preview only |
| F / step 4 | `frontend/src/features/staff/eventProgramme/**`, `EventBroadcastsPanel.tsx`, `EventAnalyticsPanel.tsx`: broadcasts/analytics/readiness empties |
| P / step 4 | `frontend/src/components/delight/**`, `frontend/src/features/{accountSavedDetails,landing}/**`: five moods, loader, tag, four robot poses, saved-details empty, demo and shared pass; motion/keyboard/status behavior |
| G / steps 4–5 | Seed install/revision/purge wiring, real consumer screenshots and AA/forced-theme/reduced-motion audit in `frontend/e2e/events-programme.spec.ts`; final Impeccable and review record |

ARTWORK signs: complete source inventory, themed vectors, seed geometry/resources,
local six-certificate/36-badge proof inventory and static accessibility contract.
E signature: **pending authoritative renderer acceptance**. Consumer lane import
signatures and G visual/Impeccable acceptance: **pending integration**. No consumer
is falsely marked integrated because its illustration exists.

## UNFINISHED — scheduled before integration acceptance

1. **G verification, step 5:** run
   `tests/events/programme/default_templates/test_inventory.py` through the isolated
   backend runner. LF rerun list: `scratchpad/ev/ARTWORK-rerun-files.txt`.
   Both new test files are ignored by the repository's broad test ignore rules;
   preserve them explicitly when collecting this lane (no staging was performed).
2. **E, steps 4–5:** replay `T/schema_fixtures.json` through the authoritative seed
   validator/server PDF renderer; verify every photo/no-photo combination, CJK/RTL
   fallback, actual-size QR quiet zone/scan and a real consented member badge.
   Extend/run `backend/tests/events/programme/{certificates,credentials,profile_photos}/**`.
   No real member/credential samples may be committed.
3. **A/B/C/D/E/F/P plus G, steps 4–5:** complete the exact imports above and per-screen
   alt/decorative, light/dark, reduced-motion, keyboard and forced-theme acceptance;
   all twelve actual empty areas must be visibly integrated. Run lane UI tests and
   `frontend/e2e/events-programme.spec.ts` before accepting decision 32.
4. **Orchestrator/G, before final acceptance:** independently review these owned
   files and correct findings, then record E/consumer/G signatures and final
   Impeccable/owner QA. CLI review could not run in this lane's environment.
