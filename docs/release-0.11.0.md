# SpaceWorks 0.11.0

> **Superseded.** The 0.11.0 candidate was never published; its changes ship in 0.12.0. This notes is kept as history — use the [0.12.0 notes](release-0.12.0.md).

SpaceWorks 0.11.0 brings a separate Inventory page, clearer account histories, delegated public-stat settings and expanded staff workflows.

## For members and makerspaces

- A makerspace opens on an overview of its events and enabled areas. **Inventory** has its own page. The existing banner appears on the overview and directory card; an uploaded makerspace logo replaces the default tenant-header branding. Light mode is the default, with saved theme choices preserved.
- **Your history** links to your own borrowing and returns, event participation, bookings, Shop orders, payments and receipts. Account-only borrowers can read their own lending history without enabling the membership dashboard. The core payment ledger remains available without the online payment rail.
- Area managers can choose the public-stat figures and lists they are authorized to manage. Settings grants and locks apply on the server; the public page and TV board use the same visibility choices and existing privacy rules.
- Shop configuration covers products, variants, images, stock, member prices, tax, holds, pickup, returns, receipts and reminders. Orders show pickup progress and their recorded payment and return history. If an event pickup becomes unavailable, buyers and Shop staff see a prompt to confirm another arrangement with the makerspace. The order keeps its original pickup history.

- New online machine and print requests require an active membership at that makerspace, an active check-in and acceptance of the current waiver when required. Ask staff about access if the online form is unavailable. Previously created jobs remain subject to their existing history rules.

## For staff and event organisers

Events and hackathons support configurable applications, file/link requirements, submission stages, reviews, judging, public galleries, crew and mentor workflows, ticketing, recorded reimbursements and prize payouts. Card and certificate tools include configurable designs, print sheets, approval controls, verification and revocation. Event ID cards and ticket designs keep independent switches: turning off certificate design does not hide the other enabled credential tools. QR revocation uses a fresh makerspace-scoped row and keeps its mutation and audit in one transaction, including callers outside the API.

Technician and Shop Manager roles have their own scoped workflows. Lending, maintenance, repairs, stocktake, reports and scheduled notifications follow their source modules and features. Switching an area off keeps its records; the [switch-off reference](MODULES-OFF.md) explains the retained-history and existing-obligation exceptions. Disabling new asset-unit generation retains existing unit records and authorized servicing/returns under core inventory authority, state and audit checks; it cannot create new units or QR identities.

Authorized staff can preview and download an equipment CSV from the event overview or exact booking row when Reports and the source area are enabled. See [equipment reports](equipment-reports.md) for the counted loans and required access.

English is the bundled language. The language switcher and message catalogues support future language packs. The in-app Help centre provides task guides matched to role and enabled areas; [user manuals](USER-MANUALS.md) lists the starting points.

## For operators

The web superadmin console includes space lifecycle controls, platform reporting and audit search, and recovery visibility. The Django control plane is server-only by default, with the existing opt-in proxy and separate tunnel configuration. Personal API tokens and connected-app controls remain account-scoped.

Self-hosting remains the primary path. The [operator manual](operator-manual.md), [hosting comparison](choose-your-hosting.md), [upgrade guide](upgrade-to-0.11.0.md) and [security verification summary](security-summary-0.11.0.md) cover deployment and the checks required for this candidate. The settings split preserves the established import interface and profile behavior.

## Verification and accepted sample limits

This is release-candidate documentation. The complete backend regression, final browser/role/module/money matrix, responsive visual review, deployment and old-version upgrade rehearsals, final generated API/client and exact final-image checks are still in progress. Earlier passing results do not establish that every release gate is green.

Four additional card/programme/import/print browser stories passed together on the 7 November candidate, including actual A4 and Letter jobs and approved/active-only output. The rendered PDFs' five QR symbols decoded and verified successfully. These are software-output checks: a physical CR80 printer and physical A4 duplex printer have not been exercised. Their manual acceptance remains recorded separately.

Two memory-heavy local tests remain explicitly deferred under the approved 8 GB test limit: `tests/account_split/test_p1_data_migration.py` and `tests/makerspaces/test_rbac_f6_backfill.py`. Their deferral does not waive the other migration or runtime checks.

Actual open-format exports were checked from Inkscape, FreeCAD, KiCad, Arduino CLI, Bambu Studio and PrusaSlicer, including UF2 and binary G-code. Release 0.11.0 waives real proprietary samples for SolidWorks, Inventor, Fusion, Altium, Eagle, LightBurn, CorelDRAW, SketchUp and DWG because owner samples were not supplied. PES/DST embroidery samples are waived if Ink/Stitch remains unavailable. File-format acceptance is separate from browser preview, upload authorization and storage verification.
