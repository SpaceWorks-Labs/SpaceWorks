---
title: Set up machine types and their consumables
group: How-to guides
order: 258
summary: Add any machine type from a template, choose what it uses up and in which units, price it, link stock, and record use on jobs.
---

# Set up machine types and their consumables

A 3D printer, a laser cutter and a PCB mill do not use the same things, or count them the same way. From 0.12.0
each machine type has a **consumable profile** in your space: the list of what a job on that type uses up, in that
type's own units. **Add a machine type** is one step-by-step setup for any machine, prefilled from a template.

## Add a machine type

Machines › **Add machine type**. Pick a template (or **Start blank**), then work through the steps. Every step can be
changed later: on a type's page, Settings › **Edit type setup** opens the same editor.

1. **Basics** — name, icon, how the type is metered (minutes, weight, volume, length, count), whether it is booked,
   and whether new machines of the type appear publicly.
2. **Consumables** — the profile (below).
3. **Job and intake fields** — the questions a member answers when asking for a job (text, number, whole number,
   choice, yes/no; required or not), and the type's job settings.
4. **Pricing** — the type's price per minute, per unit and per job, through the existing pricing screens. Members and
   non-members are priced differently with automatic discounts.
5. **Access** — machine access grants, "open to all members" and supervised sessions ([machine access](machine-access.md)).
6. **Bookings** — the type's booking defaults: slot length, buffers before and after, and whether staff approve.
   Every new bookable space for this type (or one of its machines) starts with them; **Apply to existing spaces**
   updates the type's current spaces through the normal booking rules, so it needs booking authority.
7. **Safety and adapter profile** — idle auto-off, maximum session, area-clear and filter checks, used by machine
   adapters (only when machine integrations are on).
8. **Maintenance** — suggested schedules by hours, jobs or days.
9. **Notifications** — which staff get this type's machine-service job notices (submitted, quoted, accepted, started, completed, failed, cancelled and the rest), plus its stock, adapter and maintenance alerts. These are ordinary notification
   recipient rules narrowed to the machine type, the same ones Settings › Notifications shows; there is no second
   system.
10. **Documents and training** — notes members read before using the machine, and files (PDFs, images) stored privately
   and counted against the space's storage. Members see them on the machine type, and, if you choose, when starting a
   session and when asking for a job. A file can be kept staff-only.
11. **Add machines** of this type.

Only the Space Manager adds a machine type. A Machine Manager whose role covers a whole type can edit that type's
consumables and apply a template's consumables to it.

### Templates are data

The built-in templates (FDM 3D printer, resin printer, laser cutter, PCB mill, CNC router, vinyl cutter, embroidery
machine, sewing machine, soldering station, ceramics kiln, generic time-based machine) ship as a data file. On the
Machines page, **Machine type templates** lets the Space Manager save an edited copy of one (it replaces the built-in
for your space only) or duplicate it as a new template, and edit every section of it (consumables, intake questions,
pricing hint, access, bookings, safety, maintenance, job, notifications, training notes) with the same forms as the
wizard; the server checks it before saving. **Revert to built-in** deletes the copy. Applying a template never overwrites:
consumables you already have are skipped, and a type's intake questions are only filled when it has none.

## The consumable profile

Each row has:

| Setting | What it means |
|---|---|
| Name and key | What staff and members see, and the stable key reports and adapters use (`filament`, `sheet`). |
| Kind | Material stock, tool wear, time, fixed per job, or other. |
| Unit | g, kg, mm, m, ml, l, cm², m², cm³, sheet, piece, min, h, use, or 1,000 stitches. Sheets, pieces and uses are whole numbers. |
| Choices | Materials, colours, thicknesses and sizes on offer. An empty list means free text. |
| Required on a job | A completed job must record how much was used. A failed job does not need it. |
| Estimated by | Nobody, the member when asking, staff when quoting, or the job file (the member copies the slicer's figure). |
| Recorded by | Who may record the actual: staff (always), the member, and/or a machine adapter. |
| Price per unit | Optional. Empty means it is not charged separately. |
| Stock | A consumable pool in matching units (g/kg to grams, ml/l/cm³ to millilitres, mm/m to millimetres, sheet/piece/use to count) or an inventory item (whole units only). |

Removing a consumable that jobs already used switches it off instead, so job history keeps its meaning. Its unit is
fixed once used; add a new consumable for another unit.

## On a job

- **Asking for a job** shows only the consumables the member estimates, with their units and choices.
- **Quoting** staff can add estimates; the quote prices each consumable that has a price, at the current price.
- **Completing** records the actual use: staff in the complete dialog or the job's **Consumables** item, the member
  under **What your job used** on their job page once it is accepted, or the machine adapter's report. Each consumable is recorded **once** per job; a different second amount is refused. Recording
  draws the linked stock in the same step: a pool through its ledger (with the existing low-stock To-Buy alert), an
  inventory item through Inventory Availability. If stock is short, the pool is drawn to zero and the shortfall is
  audited for staff to correct, because the material was already used.
- **The charge** goes through the existing machine-service charge: each priced consumable becomes a line at the price
  recorded with it. A job charged "material used only" after a failure keeps the material lines. Nothing is charged
  when charges are switched off, and money owed is tracked whether or not online payments are on.
- **Adapters** report measured use by key in `job.report` `profile_consumptions` ([adapter API](../device-adapters/api.md)).
  A key the type does not list is refused with `unknown_consumable_key`.
- **Reports** › Machines › **Consumables by machine type** sums estimates, actuals, adapter-reported amounts and the
  value of what was used, per type and consumable.

### The type's own price still applies

A profile price is **in addition to** the type's time, material and per-job prices. Do not set both a material rate on
the type and a price on the consumable that measures the same material, or a job pays twice for it.

## Upgrading from an earlier release

Nothing is deleted or re-priced. Each per-machine consumable becomes a row on its machine's type (grams as `g`, an
inventory item as `piece` linked to that item), and each type with a material catalogue or a consumable pool gets a
**Material** row in its metering unit with those materials and colours as choices. None of them has a price of its own
or is required, so existing jobs, quotes and adapters behave exactly as before.

## What each machine uses, and how spaces bill it

Research behind the templates. Rates are examples from public price lists, not recommendations.

| Machine | Consumables (unit) | How spaces bill it | What a job file or adapter can report |
|---|---|---|---|
| FDM 3D printer | Filament (g; material, colour), nozzle wear (h) | Per gram, e.g. PLA $0.05–0.10/g, ABS/PETG $0.20/g, often with a per-plate fee [4][2][3][5] | PrusaSlicer `; filament used [mm]`/`[g]`/`[cm3]` and `estimated printing time`; Cura `;Filament used:` (m) and `;TIME:`; Bambu header weight; Moonraker `filament_used` (mm); OctoPrint `filament.tool0.length/volume` [6][7][8][9][10][11] |
| Resin printer | Resin (ml), IPA (ml), FEP film (use), gloves (piece) | Per ml, about $0.10–0.15/ml; IPA and film usually folded in [4][5][2] | PrusaSlicer `.sl1` `usedMaterial` [12] |
| Laser cutter | Sheet stock (sheet, or cm²; material, thickness, size), lens wear (h) | Per sheet (e.g. 1/8" plywood $5, acrylic $8.95) plus machine time (e.g. per minute after free minutes) [5][4][3][13] | Job time only (inferred) |
| PCB mill | Copper-clad board (piece), end mills and V-bits (use) | Per board (e.g. FR4 $8); bits as wear [5][15] | CAM time and tool list (inferred) |
| CNC router | Sheet stock (sheet) or stock volume (cm³), bits (use) | Per sheet or board foot, plus time (e.g. $45/h staff-run) [5][4][13] | CAM machining time and tools (inferred) |
| Vinyl cutter | Vinyl (m; type, colour), transfer tape (m) | Per linear foot or square foot (e.g. $4/ft, $1–2.50/sq ft) [17][18][5] | None standard |
| Embroidery | Thread (1,000 stitches; colour), stabiliser (per job) | Per 1,000 stitches (e.g. $0.10) plus stabiliser per job [5][17] | Stitch count from the design (inferred) |
| Sewing | Fabric (m), needles (piece) | Fabric per yard or area; thread usually free [4][5] | — |
| Soldering | Solder (g), tips (piece), components (piece) | Usually in membership; components per count [4] | — |
| Ceramics kiln | Firing (per job; bisque/glaze, load size), ware volume (cm³) | Per cubic inch (e.g. $0.05–0.07), per firing or per shelf [19][20] | None; staff enter it |
| Any machine | Time (min) | Per 5–10 minutes or per minute of use [1][21][22] | Session minutes |

Sources (consulted 2026-11-12):

1. Makerspace time-based fee pages (Dallas Makerspace, Artifactory) and the Fabman forum thread "Charging through Fabman", https://forum.fabman.io/t/charging-through-fabman/200
2. Texas A&M-CC I-Create lab prices, https://www.tamucc.edu/library/visit-study/icreate-lab/prices/index.php
3. UBC eHUB costs, https://eng-services.ece.ubc.ca/ehub/costs; Michigan State makerspace FAQ, https://lib.msu.edu/makerspace/faq; University of Arizona CATalyst fees, https://lib.arizona.edu/catalyst/equipment/fees
4. Northeastern Makerspace at EXP price list, https://makerspaces.northeastern.edu/?p=1527
5. Chapman University DCI materials cost sheet, https://www.chapman.edu/engineering/facilities/materialssheet.aspx
6. Printago, filament usage in G-code, https://printago.io/blog/gcode-filament-usage
7. Prusa forum, duration and filament usage, https://forum.prusa3d.com/forum/prusaslicer/how-to-get-duration-and-filament-usage-on-cli/
8. Duet3D forum on Cura headers, https://forum.duet3d.com/post/9789
9. Bambu G-code reference (rjduran/bambu-gcode-reference, mirror consulted), https://gh.r-mj.com/rjduran/bambu-gcode-reference; Bambu forum, https://forum.bambulab.com/t/total-filament-not-calculating-correctly/106051
10. Moonraker history API, https://moonraker.readthedocs.io/en/latest/external_api/history/
11. OctoPrint job API, https://docs.octoprint.org/en/master/api/job.html
12. Prusa SL1 file format, https://help.prusa3d.com/glossary/file-sl1-sl1_141519
13. University of Maryland Terrapin Works pricing, https://terrapinworks.umd.edu/pricing
14. LightBurn job time estimate (inferred; not fetched)
15. Fab Lab inventory (inventory.fabcloud.io), PCB milling bits for the SRM-20
16. Fusion 360 setup sheets (inferred; not fetched)
17. Ajax Library makerspace price list, https://ajaxlibrary.ca/node/1903
18. Rutgers Makerspace graphic cutters, https://makerspace.rutgers.edu/services/graphic-cutters
19. Woodstock Guild ceramics firing fees, https://www.woodstockguild.org/ceramics-firing-fees/
20. Ceramic Arts Network and studio fee pages (per firing and per shelf)
21. Fabman product page, https://fabman.io/product
22. "New in Fabman: Credits", https://fabman.io/blog/new-features-credits/
