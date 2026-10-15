# Yuyu UX patterns → SpaceWorks screen spec

Status: research input for `docs/design-revamp/PLAN.md` Phases 0 and 2–6. No app code is changed here.
Scope: layout, information architecture, interaction, states and copy structure. Colour, type
families, logo and icons come from the brand spec (PLAN §3.1–3.3). Where this document says
"primary fill" it means whichever token wins PLAN open question 3 (teal or Deep Ink). Yuyu uses a
near-black pill.

Sources: 28 Yuyu screens in 4 boards, each cropped one per file into the scratchpad
`crops/` folder (`full-org1..6`, `full-mgr1..4`, `full-auth1..7`, `full-att1..8`,
`top-att3..11`). All app screens are **1280 px wide** (the attendee ticket is 390 px), so every
measurement below is a native pixel count read off the crop. Treat values as ±2 px. SpaceWorks
components were read in this worktree at `d3e5ed29`.

| Ref | Yuyu screen | Board |
|---|---|---|
| Y1 | Organiser home ("Good morning, Priya", org cards, Coming up, Recent activity) | Organiser workspace |
| Y2 | Org Events list (callout, 4 stat cards, tabs, date-chip rows, activity rail) | Organiser workspace |
| Y3 | New organisation form + live public-page preview | Organiser workspace |
| Y4 | Members (invite-link card, table, dashed empty state) | Organiser workspace |
| Y5 | Settings › General (settings rows, Discard/Save, danger zone) | Organiser workspace |
| Y6 | Settings › API access (form card, checkbox cards, code block, accordions) | Organiser workspace |
| Y7 | Event › Overview (detail header, 8 tabs, stat cards, latest list, At a glance, CTA card) | Managing an event |
| Y8 | Event › Check-in (progress stat, offline callout, camera, find, toggles, recent + Undo, door station) | Managing an event |
| Y9 | Event › Page & programme (segmented control, track chips, session cards, delay stepper) | Managing an event |
| Y10 | Series › Overview (upcoming-date cards, details form, radio chips, agenda, danger zone) | Managing an event |
| Y11 | Sign in (split screen) | Sign in, invites & account |
| Y12 | Set a new password (centred card, strength meter) | idem |
| Y13 | Confirm your email (centred card) | idem |
| Y14 | Org invite accept (avatar pair, role pill) | idem |
| Y15 | Event co-organiser invite (banner card) | idem |
| Y16 | Account › Profile (settings rows, verified pill) | idem |
| Y17 | Account › Security (big callout with button, destructive outline) | idem |
| Y18 | Public event page with cover + sticky "Join this event" card | Attending an event |
| Y19 | Same page, no cover, tenant accent colour | idem |
| Y20 | Public programme (time grid, track filter pills) | idem |
| Y21 | Public session detail (right rail "Next on main stage") | idem |
| Y22 | Speaker page | idem |
| Y23 | Series event page (inline register form inside sticky card, date pills) | idem |
| Y24 | Live running order (NOW / NEXT / LATER, delay pill) | idem |
| Y25 | Feedback form (rating tiles) | idem |
| Y26 | Mobile ticket with QR (390 px) | idem |
| Y27 | Kiosk: enter station PIN (digit boxes + keypad) | idem |
| Y28 | Kiosk: door check-in station (camera + big result card + Undo + recent) | idem |

---

## 1. Pattern catalogue

### 1.0 Observed scale (use these, not ad-hoc values)

- **Spacing steps actually used:** 4, 8, 12, 16, 20, 24, 28, 32, 36, 40. Card-to-card gap is
  **12**; section-to-section gap is **32–40**; page gutter beside the sidebar is **36**.
- **Radii:** nav pill 8 · input, card, table container, stat card 12 · callout 14 · camera and
  large blocks 16 · centred auth card 20 · kiosk panels 24 · auth brand panel 28 · buttons, chips
  and pills fully round.
- **Type sizes (px):** 11 caps (date-chip month, ticket labels) · 12 caps with +0.08em tracking
  (eyebrows such as "ORGANISATIONS", "PUBLIC PAGE PREVIEW", "RECENT") · 13 small meta and helper ·
  14 meta lines, table cells, sidebar sub-items · 15 nav items, buttons, tab labels, body UI ·
  16 row titles and settings labels · 20 section headings ("Coming up", "Recent activity") · 22
  sticky-card title · 32–40 page titles (bold, tight tracking about −0.02em) · 52 kiosk and
  centred-hero titles · ~70 public event title.
- **Weights:** only regular, semibold and bold. Bold is reserved for titles, numbers and the
  name inside an activity sentence.
- **Borders:** 1 px warm hairline everywhere. Shadows only on floating things (auth hero cards,
  segmented thumb, sticky join card, very soft). Cards are flat, bordered and white on an
  off-white app canvas. The sidebar is a slightly darker off-white with a right hairline.
- **Control heights:** header buttons 44 · auth and full-width buttons 50–52 · inputs 48–50 ·
  inline pill actions 28 · status pills 20–22 · nav items 40 · table rows 64 · list-card rows 82
  · kiosk keys 76.

### P1. App shell and sidebar (Y1–Y10, Y16, Y17)

```
┌──────────── 240–300 ────────────┬───────────────────── main ─────────────────────┐
│ [Y] Yuyu                         │  36px gutter                                   │
│ ┌─────────────────────────────┐ │                                                │
│ │[SD] Screenshot Demo Coll… ⇕ │ │                                                │
│ │     Owner                    │ │                                                │
│ └─────────────────────────────┘ │                                                │
│ ▣ Events            (active)    │                                                │
│ ◌ Series                         │                                                │
│ ◌ Members                        │                                                │
│ ◌ Settings                       │                                                │
│     General      (sub-items     │                                                │
│     API access    when active)  │                                                │
│                                  │                                                │
│ View public page ↗               │                                                │
│ (PO) Priya Organiser             │                                                │
│ Sign out                         │                                                │
└──────────────────────────────────┴────────────────────────────────────────────────┘
```

- **Width:** 240 on the cross-org home and 298 inside an org. The settings and account crops
  show 380–400, which is a screenshot artefact rather than a rule. **Spec: 264 fixed at ≥1024
  px.** That leaves 1280 − 264 − 72 = 944 px of content.
- **Logo row:** a 30 px rounded tile plus an 18 px bold wordmark. Top and left inset 22.
- **Workspace switcher card:** 14 px side inset, 58 px tall, radius 10, 1 px border, white fill.
  It holds a 30 px rounded-6 avatar tile (org colour, initials), the name at 14 semibold
  (truncated with an ellipsis), the role at 12 muted, and an up-down chevron on the right. The
  whole card is one button that opens a menu.
- **Nav item:** 40 tall with a 43 px pitch (3 px gap), radius 8, 14 px inset from the sidebar
  edge, 10 px text padding. An 18 px line icon, 10 px gap, then the 15 px label. **Active:** a
  filled warm-grey pill and a semibold label; no accent bar and no coloured text. The home
  sidebar (Y1) has no icons. The org sidebar has icons on the four top items only.
- **Section label:** "ORGANISATIONS", 12 caps tracked and muted. 24 px above, 8 px below.
- **Sub-items** appear only under the active parent: 14 px labels indented 24, with the same
  active pill. Y5 and Y6 show Settings › General / API access.
- **Bottom block,** pinned with `margin-top:auto`: a "View public page ↗" text link (14), a user
  chip (24 px initials circle plus name; it becomes a filled pill while on Account), then
  "Sign out" as plain text. **There is no theme toggle and no help item in the sidebar.**
- **Interaction:** the sidebar never scrolls on Yuyu because it has 4 items. SpaceWorks needs
  its own scroll region (see §2). The active state comes from the route.

### P2. Page header (Y1, Y2, Y4–Y6, Y16)

```
Good morning, Priya                       ← 15 muted (greeting or date line)   y+40
Events                         [ New series ] [■ + New event ]  ← title 40 bold; buttons 44h
People who can work on this organisation's events.   ← optional 15 muted subtitle, 8 below
```

- **Eyebrow line,** above the title: either a date ("Wednesday, 14 October") or a greeting
  ("Good morning, Priya"). It appears only on landing screens (home, events). Inner pages use a
  **subtitle under the title** instead: one sentence that names the scope and what saving does
  ("How Screenshot Demo Collective appears to the public. Changes go live when you save.").
- **Actions** sit right-aligned on the title baseline row: **at most one filled primary pill
  plus one outline pill.** Primary text is 15 semibold with 20 px horizontal padding. A "+"
  glyph prefixes create actions. The secondary pill is an outline on white.
- 24 px from the header block to the first content element.

### P3. Detail header with back link, identity chip and underline tabs (Y7–Y10)

```
← All events                                              13 semibold link
┌OCT┐ Demo Summit 2026                     [ View page ↗ ] [■ Open check-in ]
│14 │ (Published) Public · Tomorrow, 9:30 AM
└───┘
Overview  Guests  Page & programme  Registration form  Invites  Check-in  Feedback  Settings
━━━━━━━━──────────────────────────────────────────────────────────────────────── (full bleed)
```

- **Back link:** "← All events" at 13 semibold. It is the only breadcrumb, 32 px above the title.
- **Identity chip:** 52×52 (see P7). The title is 34 px bold. 14 px gap between chip and title.
- **Meta line:** the status pill (P10) first, then "Public · Tomorrow, 9:30 AM" at 14 muted,
  separated by " · ".
- **Contextual primary:** "Open check-in" on Overview. On the Check-in tab the primary
  **disappears** (Y8) and only "View page ↗" stays. On Page & programme it becomes
  "View programme ↗" (Y9). **Rule: the header primary never points at the screen you are on.**
- **Tabs:** 15 px labels, 12 px horizontal padding, a 40 px tall bar. The active tab is ink and
  semibold with a 2 px ink underline as wide as the label plus its padding. Inactive tabs are
  muted. A 1 px hairline runs **full bleed across the main area**, not just the content column.
  Tabs are links (URL-addressable). With 8 tabs on 944 px they fit on one line; below that they
  must scroll horizontally with edge fades (Yuyu does not show this).
- Series uses a **coloured icon tile** (a recurrence glyph on a purple 52 px tile) instead of a
  date chip. **Generalisation: every detail page has an identity tile; a date where one exists,
  otherwise a type icon or initials.**

### P4. Stat-card row (Y2, Y7, Y8)

- **Grid:** 4 equal columns with 12 gaps, 102 tall, radius 12, 1 px border, 16 px padding.
- **Anatomy:** label at 14 muted on top, number at 28–30 bold 12 px below. Variants:
  - **Fraction:** "5 / 120" with the denominator at 16 semibold muted.
  - **Progress:** a 4 px track (8 px on check-in) with the fill in the accent colour, 12 px
    below the number.
  - **Wide stat:** spans 1.5–2 columns (Y8 "Checked in 2 of 5 · 40%") with a callout beside it.
- **Not clickable** in Yuyu. **SpaceWorks deviation:** stat cards that represent a queue are
  links to the filtered list (the dashboard does this today). Keep the card flat but give it a
  hover border and focus ring.
- Zeros are shown as "0", not hidden (Y7 "Waiting for approval 0").

### P5. Contextual callout (Y2, Y6, Y8, Y17, Y7 CTA card)

Three sizes, all in warm-yellow fill with dark-brown text, radius 14, no border:

1. **Banner** (Y2): one line, 50 tall, full content width, 16 px padding. A circled "!" icon,
   then a **bold lead clause** ("Demo Summit is tomorrow.") and a regular follow-on
   ("Download the guest list for offline check-in before you leave."). A right-aligned
   underlined bold link with "→" ("Prepare check-in →").
2. **Panel with button** (Y8, Y17): two lines, about 105 tall. A bold title ("Not ready for
   offline yet", "Two-step sign-in is off"), one sentence of consequence, and a **filled
   dark-brown pill button** on the right ("Download guest list", "Set up authenticator").
3. **CTA card** (Y7 "Get the door ready"): sits in a side column, the whole card is a link, with
   a bold title, a body line and a "→" at the right.
4. **Inline advisory** (Y6): one line, "!" plus text, no action ("Keep keys in a secret manager.
   Never put them in browser code, URLs, source control or logs.").

**Rules observed:** a callout exists only when something is **time-sensitive or unsafe and the
user can act now**. There is never more than one on a screen. It always names the consequence.
There are no info-blue "tips". **A callout replaces a toast or banner for standing conditions.**

### P6. List rows as bordered cards (Y1, Y2)

```
┌──────────────────────────────────────────────────────────────────────────┐
│ ┌OCT┐  Demo Summit 2026                                   5 / 120 going   │ 82 tall
│ │14 │  Tomorrow, 9:30 AM · Bangalore International Centre ▬───────────    │
│ └───┘                                                                     │
└──────────────────────────────────────────────────────────────────────────┘ 12 gap
┌ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─┐
  ┌NOV┐  Volunteer onboarding                              (Finish & publish)   ← draft: dashed,
  │12 │  Draft · only your team can see it                                        grey fill/chip
└ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─┘
```

- Card: radius 12, 1 px border, 16–18 px padding. The whole row is a link to the detail page.
- Left: an identity chip. Middle: the title at 16 semibold and a meta line at 14 muted with
  " · " separators and **relative time words** ("Tomorrow", "In 9 days", "Every Tuesday").
- **Right slot holds exactly one thing,** chosen by state:
  - progress: "**5** / 120 going" with a 110 px × 4 px bar;
  - a **yellow action pill** (28 tall, 13 semibold, brown text): "Prepare check-in",
    "Finish & publish". This is the row's next step;
  - a **two-line nudge**: muted state ("No guests yet") over a teal text link ("Send invites").
- **Drafts:** dashed border, off-white fill, grey chip, and meta that says who can see it
  ("Draft · only your team can see it").
- Y1 "Coming up" uses the same row with the action pill only on the most urgent item.

### P7. Date chip / identity tile

- **Size:** 52×52 in rows and headers (54 on the event list), radius 8, 1 px border.
- **Top band:** 18 px, coloured fill, month at 11 caps bold white. **Body:** white, day at 20
  bold ink.
- **Band colour is stable per event** (identity hash): orange, indigo, teal. Drafts get grey.
- Variants: initials tile (org avatar: rounded square, coloured fill, white initials), person
  avatar (circle, pastel fill, coloured initials at 11 bold), icon tile (series).

### P8. Underline tabs with inline counts (Y2, Y7, Y16)

- On list pages the tabs **are the filter** ("Upcoming · Drafts 1 · Past"). The count follows
  the label in the same muted weight with no badge background. A count is shown only where it
  is actionable (Drafts) or small, never on "Past".
- Tabs sit **between** the stat row and the list, aligned to the main column (not full bleed on
  list pages; full bleed on detail pages).

### P9. Segmented control (Y9, Y11)

- A grey track pill 44–50 tall with a white thumb, soft shadow and semibold active text.
- **Use:** two to three mutually exclusive **views of the same object** ("Page content |
  Programme"; "Sign in | Create account"). It never replaces navigation tabs.

### P10. Pills and chips

- **Status pill:** 20–22 tall, 8 px horizontal padding, 12 semibold, tinted fill with dark text
  in the same hue. Observed: Published, Going, Verified and Unused in green; Waitlist and
  "Running 5 min late" in yellow; Owner and "as a Member" in grey; Live in green with a 6 px dot.
- **Meta chips** (Y6, Y18): grey tint, 26–28 tall, 13 regular ("Bearer auth", "In person",
  "3 sessions · 2 speakers"). The first chip may carry the brand tint ("Free").
- **Choice chips** (Y10 "Who can join"; Y20 track filter; Y23 dates): 36 tall outline pills. The
  selected one has a 1.5 px dark border (Y10) or a dark fill with white text (Y20 "All tracks").
- **Track tag** (Y18 schedule): a tinted pill aligned right in the row.

### P11. Buttons

- **Primary:** filled near-black pill, white 15 semibold, 44 tall in headers and 50–52 full
  width in auth. One per view region.
- **Secondary:** a white outline pill with a 1 px border and the same height.
- **Tertiary:** an underlined text link (13–15 semibold), used for "Forgot?", "Back to sign in",
  "Switch account", "Undo", "All guests →".
- **Destructive:** red text ("Revoke", "Turn off station") for low-stakes reversible actions; a
  red **outline** pill with a trailing "…" ("Delete organisation…", "Delete series…",
  "Sign out everywhere") for actions that open a confirmation. Destructive is never filled.
- **Callout button:** a filled dark-brown pill inside a yellow callout.
- **Disabled:** a grey fill with grey text (Y27 "Open check-in"), not reduced opacity.
- **Paired form footer:** "Discard" (outline) and "Save changes" (primary), right-aligned at the
  end of the form. On a create form the pair is "Create organisation" (primary, left) and
  "Cancel" (plain text, right of it).

### P12. Recent-activity rail (Y1, Y2)

- A right column 260 wide with a 28 px gap from the main column (main is 622). Heading
  "Recent activity" at 20 bold.
- **Item:** a 32 px pastel initials circle, 12 px gap, then a sentence at 14 with the **actor's
  name in bold** and the target after " · " ("**Kiran Reddy** joined the waitlist · Demo
  Summit"), with the relative time at 14 muted on the next line. 77 px pitch. No dividers.
- Footer link: "See all activity →", underlined 14 semibold.
- The rail **sits beside the list, not above it,** and starts level with the tab bar (Y2) or the
  first section heading (Y1). It drops entirely on narrow screens (inferred).

### P13. Key–value "At a glance" card (Y7)

- A bordered card 280 wide with 42 px rows split by hairlines. Label at 14 muted on the left,
  value at 14 ink **right-aligned**. Below it, the CTA card (P5.3).

### P14. Tables inside a card (Y4, Y8, Y10)

- One bordered card radius 12. Header row 40 tall with labels at 13 muted, sentence case, no
  uppercase. Body rows 64 tall with hairlines.
- Person cell: a 36 px initials circle, name at 15 semibold plus "(you)" muted, and email at 14
  muted below.
- The last column is a row menu ("—"/"⋯") or an **inline text action** ("Undo", underlined).
  The agenda table (Y10) puts the status pill right-aligned.

### P15. Settings rows (Y5, Y16, Y17)

```
Logo                               [SD]  ( Upload logo )
Square works best. JPEG, PNG or…
───────────────────────────────────────────────────────────────── hairline
Name & description                 Name
Shown at the top of your public    [ Screenshot Demo Collective          ]
page.                              Description
                                   [ A demo organisation used to…        ]
───────────────────────────────────────────────────────────────── hairline
Web address                        [ yuyu.idliapps.com/  shots-org   Copy ]  (read-only: grey fill)
Set when the organisation was created.
─────────────────────────────────────────────────────────────────
                                              ( Discard ) [■ Save changes ]
┌───────────────────────────────────────────────────────────────────────────┐
│ Delete organisation                                 ( Delete organisation… )│ red border
│ Permanently removes every event, registration and membership. This can't  │
│ be undone.                                                                 │
└───────────────────────────────────────────────────────────────────────────┘
```

- **Columns:** left 290–310 (label at 16 semibold and a helper at 14 muted that explains the
  effect), right is the remaining width. 24 px vertical padding per row, hairlines between rows.
- **Read-only values** use a grey-filled field with an inline action ("Copy") or a status pill
  ("Verified"). A lock-style icon marks one that cannot be edited, and the helper says why
  ("Changing email is coming in a future update.").
- **Footer:** one Discard/Save pair for the whole page. The account page puts a meta fact on the
  left of the save row ("Member since 13 October 2026").
- **Independent action rows** (Y17 password) carry their own button inside the right column
  ("Update password"), because they are not part of the page save.

### P16. Danger zone (Y5, Y10)

- Always last, 40 px below the save row. A card with a 1 px pale-red border, radius 14 and
  20 px padding. Title at 16 semibold red ("Delete organisation"), one sentence of consequence
  at 14 ink, and a red outline pill with "…" on the right. **One danger card per irreversible
  action.**

### P17. Empty states (Y4, Y6, Y3 preview)

- A dashed-border card (1 px dashed, radius 12, 20–24 px padding) with **one centred sentence**
  at 15 muted. **No illustration and no heading.** The sentence states the situation and the
  next step **by pointing at a control already on screen**: "It's just you so far. Copy the
  invite link above to bring in your team." / "No clients yet. The secret key appears once,
  right after you create one." / "Your events will appear here".
- The same dashed treatment marks **"+ Add session"** and "+ New organisation" placeholders. The
  "add" affordance sits where the next item will appear.

### P18. Create form with live preview (Y3)

- Form column 636 wide and preview column 300, gap 32. The preview is labelled with an eyebrow
  ("PUBLIC PAGE PREVIEW") and updates as you type.
- Prefixed URL input: a grey static prefix segment ("yuyu.idliapps.com/") joined to an editable
  segment, with an **inline availability check** underneath ("✓ Available" at 13 green).
- Optional fields are marked inline ("Logo Optional", "Optional · shown on your public page").
  Required fields carry no asterisk.
- Dropzone: dashed card with a 56 px icon tile, "Drop an image here, or **choose a file**" and
  the constraints line "Square, JPEG, PNG or WebP, up to 5 MB".

### P19. Form card with checkbox cards and developer reference (Y6)

- A "New API client" form inside a bordered card with 3-column inputs.
- **Checkbox cards:** a 3-up grid, each a bordered card with a checkbox, a 15 semibold label and
  a monospace scope underneath. The selected card gets a 1.5 px dark border.
- Code block: dark fill, radius 12, monospace 13, with a "Copy" button inside on the right.
  Beneath it, meta chips.
- **Accordion rows:** a disclosure triangle, the label and a monospace hint, at 52 tall with
  hairlines. This is progressive disclosure for reference material.

### P20. Session/track board (Y9)

- Track columns are tinted panels (off-white fill, radius 16, 16 px padding) with a header
  ("Main stage" plus "2 sessions" right-aligned and muted).
- Session cards inside: time at 13 semibold, title at 16 semibold, people at 14 muted, and a "⋯"
  menu. A hairline footer row holds an inline control ("Running late? [ − On time + ]") as a
  stepper pill.
- The dashed "+ Add session" sits at the end of each column. Track chips at the top carry a drag
  handle and an edit pencil, plus "+ Add track". A right-aligned muted hint explains the rule
  ("Delays only move later sessions in the same track.").

### P21. Check-in workspace (Y8)

- Top: a progress stat (2 cols) plus the "Not ready for offline yet" callout (2 cols).
- Left (446): the camera block (dark, radius 16, 240 tall, centred "Camera is off") with a
  full-width primary "Start scanning" (46) underneath. **The camera does not start until asked.**
- Right: "Find a guest" with a pill input, an outline "Find" button and a helper ("You can also
  paste a ticket link."). Below it, a settings card of toggle rows (label, helper, switch).
- "Recent check-ins" table: name and email, "10:57 PM · QR" (the method is recorded), and an
  **inline "Undo"**. "Export CSV" outline is right-aligned on the section heading.
- "Door station for volunteers" card: QR thumbnail 112, title, explanation of scope ("they can
  only check people in — no guest lists or exports"), then the buttons "Copy link" (primary),
  "Show PIN", "New PIN" and "Turn off station" (red text).

### P22. Auth split screen (Y11)

```
┌──────────────── 640 ────────────────┬──────────── 604 (16 inset) ────────────┐
│ [Y] Yuyu                             │  Free events.                           │
│                                      │  Your community's                       │
│        Welcome back.        (44 bold)│  data stays yours.        (40 bold)     │
│        [ Sign in | Create account ]  │                                         │
│        ( G  Continue with Google )   │        ╭ OCT 14 Demo Summit ╮ (rot −3°) │
│        ───── or with email ─────     │             ╭ OCT 20 Weekly call ╮ (+2°)│
│        Email                         │      (✓ Meera checked in)               │
│        [                        ]    │                                         │
│        Password            Forgot?   │                                         │
│        [                     👁 ]    │                                         │
│        [■■■■■■ Sign in ■■■■■■■]      │                                         │
│        By continuing you agree to…   │                                         │
└──────────────────────────────────────┴─────────────────────────────────────────┘
```

- Form column 400 wide, starting at x=122 and vertically centred. Headline with a full stop.
- Order is fixed: **mode switch, then social, then "or with email" divider, then fields, then
  primary, then legal.**
- The "Forgot?" link sits **on the password label row**, right-aligned. There is a show-password
  eye inside the field.
- The brand panel is a rounded (28) tinted panel inset 16 from the edges. It shows **real
  product objects** (date-chip cards, a check-in toast), slightly rotated with soft shadows.
  This is product proof, not stock art.

### P23. Centred task card (Y12–Y15)

- 440 wide (480 for invites), radius 20, 32 px padding, 1 px border, on the off-white canvas with
  the logo top-left.
- **Anatomy:** a 52 px tinted icon tile (lock, envelope) or an avatar pair, a 32 bold title,
  15–16 muted body that **names the identity in bold** ("Confirming **priya@example.test**
  activates…", "For priya@example.test. You'll be signed out on other devices."), a full-width
  primary, then a single underlined escape link ("Back to sign in", "Not you? Use another
  account").
- **Invite variant:** org tile 64 overlapping the user circle 52, a muted "You've been invited to
  join", the org name at 30 bold centred, a role pill ("as a Member"), one sentence on what that
  means and its constraints ("This invite link works once."), the primary "Accept invite", and
  a footer "Signed in as x · **Switch account**".
- **Event-scoped invite:** a coloured 110 px banner on top, left-aligned content, and the scope
  explanation in a grey inset box ("You'll get the permissions the organiser chose for you on
  this event only.").
- Password strength: a 4-segment meter (4 px bars, 4 px gaps) plus a live rule list
  ("✓ At least 12 characters" in green).

### P24. Account tabs (Y16, Y17)

- Title plus subtitle, then a 2-tab underline bar (Profile / Security) at content width, then
  settings rows.
- Security leads with a **panel callout** when a protection is off. Sessions use a destructive
  outline ("Sign out everywhere").

### P25. Public event page (Y18, Y19, Y23)

```
[SD] Screenshot Demo Collective                     Discover events  ( Sign in )   48h header
──────────────────────────────────────────────────────────────────────────────────
┌──────────────────── cover 1110×316 r16 ───────────────────────┐
└───────────────────────────────────────────────────────────────┘
(Free)(In person)(3 sessions · 2 speakers)            ┌ Join this event ──────────┐ 318w
Demo Summit 2026              (~70 bold, brand ink)   │ 5 going      115 spots left│ sticky
Build the tools your community needs.  (20)           │ ▬──────────────────────── │
┌OCT┐ Wednesday, 14 October   [⌖] Bangalore Intl Ctr  │ (MN)(DP)(SK) Meera, Dev +3 │
│14 │ 9:30 AM – 5:30 PM IST       Domlur, Bengaluru   │ [■ Register — it's free ■] │
About  Schedule  Speakers  Venue  FAQ  (anchor tabs)  │ (Add to calendar)( Share ) │
━━━━━─────────────────────────────────────────        └───────────────────────────┘
body 17/1.6, max 600                                  ┌ Hosted by  [SD] Screenshot…→┐
[18 talks][Hands-on workshops][Free lunch]  3 highlight tiles, first brand-tinted
Schedule ............................ Live schedule →
9:30 AM  Opening keynote: tools that outlast…            (Main stage)
60 min   Asha Menon
Speakers (2-col cards) · Partners (2-col) · Venue (map | text, Get directions ↗) · FAQ (disclosure)
──────────────────────────────────────────────────────────────────────────────────
[Y] Free event, powered by Yuyu                        Privacy · Terms · Hosted on Idlistack
```

- Container 1110 with 84 px gutters at 1280. Main column 545 and sticky card 318, gap 66.
- **Tenant theming** (Y19) recolours only the title, the chip tint, the date-chip band, the
  register button and the highlight tile. Everything else stays neutral, and the cover image is
  optional.
- The sticky card carries the **only primary on the page**, and it changes with state: the price
  is folded into the label ("Register — it's free"); a waitlist would read "Join waitlist". Social
  proof (avatars plus "Meera, Dev and 3 others") sits above the button; the capacity bar sits
  under the counts.
- **Inline-form variant (Y23):** the registration fields live inside the sticky card ("Join on
  20 October"; name, email, helper "We'll send your ticket and the call link here.", register;
  "Have an account? **Sign in to register faster**"). A date-pill picker sits in the main column.
- Secondary pages (Y20–Y22) **move the primary into the header** ("Register — free" pill)
  because there is no sticky card. They use a breadcrumb "Demo Summit 2026 / Programme".

### P26. Live and status pages (Y24) and feedback (Y25)

- **Running order:** a "● Live · updates automatically" green pill in the header. A **NOW** card
  in solid brand fill (white text, title 36 bold, "6:30 – 6:40 PM · 4 min left", white progress
  bar). A **NEXT** card in white with a yellow delay pill ("Running 5 min late") and the old time
  struck through ("~~6:40~~ **6:45** – 7:10 PM"). A **LATER** eyebrow list. A footnote on
  freshness ("Changes from the organisers show up here within a few seconds.").
- **Feedback:** a 590 centred column. A context eyebrow in the brand colour ("Demo Summit 2026 ·
  Wed 14 Oct"), the question as title ("How was it?"), and a reason with its payoff ("Two minutes
  of feedback… You'll get your certificate right after."). **Rating tiles** are 5 × 100×92
  bordered cards with a number and a word (Poor, Meh, Okay, Good, Loved it); the selected tile
  gets a brand border and tint. Optional fields are marked "Optional". A prefilled email carries
  a privacy helper. The full-width brand primary names both outcomes ("Send feedback & get
  certificate").

### P27. Mobile ticket (Y26, 390 px)

- "← Event page" sits beside a "✓ Confirmed" green pill. Title "You're in, Meera!" at 32 bold.
- **Ticket card:** a brand header band (org name small, event at 24 bold), a 2-column grid of
  caps labels (11) with bold values (14), a **perforation** (dashed line with half-circle
  notches), a 170 px QR, and the caption "Show this at the door. It only holds a private ticket
  link." (privacy reassurance).
- Two half-width buttons (primary "Add to calendar", outline "Save ticket") and an underlined
  destructive escape ("Can't make it? Cancel registration").

### P28. Kiosk PIN (Y27)

- Two columns on a 1180 canvas. **Left:** org tile 64, a context line ("Demo Summit 2026 · Door
  check-in"), the title at 52 bold ("Enter the station PIN"), the helper ("Ask an organiser for
  the 8-digit PIN. It unlocks check-in on this device only."), and **8 digit boxes** (46×62,
  radius 8; filled boxes show a dot; the focused box has a 2 px dark border).
- **Right:** a 3×4 keypad of 112×76 keys (radius 14, 12 gaps, digits 26 bold), with "Clear" and
  "⌫" on grey keys, and a full-width CTA "Open check-in" (58 tall) that stays **disabled grey
  until all 8 digits are in**.

### P29. Kiosk station (Y28)

- A 100 px header: event name (22 bold), "Door check-in · Station 1", and on the right a big
  count "**3** / 5 checked in", a "● Online" pill and an outline "Lock station".
- **Left:** the camera (dark, radius 24, about 590×614, white corner brackets, caption "Hold the
  ticket QR inside the frame") with a search pill and a "Find" primary underneath.
- **Right:** a **full-bleed result card** (solid green on success: 84 px check circle,
  "Checked in", name at 52 bold, "email · just now"), with "Next guest" (white pill) and "Undo"
  (white outline). Below it a "RECENT" list (✓ name, relative time). The result **is the
  screen**; there is no modal.

### P30. Undo and confirmation behaviour (Y8, Y28)

- **Inline Undo** appears in the "Recent check-ins" rows and on the station result card. Yuyu
  shows no toast and no "Are you sure?" for check-ins. Reversible high-frequency actions use
  **do it now, offer Undo in place.**
- Irreversible actions use a **danger card plus a "…" button** that leads to a confirmation.
- **Toasts do not appear on any Yuyu board.** The closest artefact is the floating
  "✓ Meera checked in" chip on the auth hero, which is a reasonable visual model. SpaceWorks
  already has `components/ui/toastStore.ts` with an awaited `undo` compensation, used by
  inventory archive. **Spec:** toast = bottom-centre (mobile) or bottom-left of the main area
  (desktop), one line plus an optional "Undo", success auto-dismisses after 8 s, errors persist.
  It is used only for **confirmations of off-screen effects** and **reversible actions whose row
  leaves the current view** (archive). Effects that stay visible confirm in place.

### 1.31 Interaction model summary

| Concern | Yuyu rule |
|---|---|
| Primary action | One per page header, one per sticky card, one per callout. Never points at the current screen. |
| Secondary | Outline pill beside the primary; everything else is a text link or a row menu. |
| Where counts live | Stat cards (overview numbers), tab labels (queue sizes), row right slots ("5 / 120"), header meta, the kiosk header. **Never** in the sidebar on Yuyu (SpaceWorks keeps its unread count there, see §2). |
| Progressive disclosure | Sub-nav only under the active parent; accordions for reference; the camera off until "Start scanning"; the live preview beside the create form; optional fields labelled rather than hidden. |
| Inline vs menu | The **next step** is inline (pill or link in the row); rare or destructive actions go in "⋯" / "—" menus; destructive-irreversible actions go in the danger zone. |
| Navigation | Back link on detail pages; breadcrumb only on public sub-pages; tabs are URLs. |
| Feedback | Inline status ("✓ Available", "Unused", "Verified"), progress bars, an Undo in place; the result card in kiosk mode. |
| States | Dashed empty cards that point at a visible control; disabled = grey fill; zero shown as "0". |

### 1.32 Microcopy style

- **Sentence case everywhere,** including buttons and tabs ("Page & programme", "Save changes").
  Caps only in 11–12 px eyebrows.
- **Headlines may end with a full stop** when they are statements ("Welcome back.", "Free events.
  Your community's data stays yours."). Task titles do not ("Set a new password").
- **Consequence first, in the helper:** "Changing it signs you out on every other device.",
  "Removes every future date and its registrations.", "This can't be undone." Helpers explain
  the *effect* of the field, not its format, except for upload constraints.
- **Name the person and the object:** "For priya@example.test.", "Signed in as …",
  "Kiran Reddy joined the waitlist · Demo Summit".
- **Numbers in context:** "5 / 120 going", "115 spots left", "2 of 5 · 40%", "3 upcoming 6 going
  1 draft", "In 9 days", "2 min ago", "Yesterday".
- **Separators:** " · " for meta, "—" (em dash) inside CTAs ("Register — it's free"), "→" for
  internal links, "↗" for anything that opens a new page or site, "…" on buttons that open a
  confirmation.
- **Reassurance at the risk point:** "It only holds a private ticket link.", "Used only to match
  your registration…", "Volunteers… can only check people in — no guest lists or exports."
- **Warm but terse:** "You're in, Meera!", "It's just you so far.", "Running late?",
  "Not you? Use another account".
- These match the SpaceWorks brand voice in PLAN §1 ("No parts added yet. Add your first item.",
  "Couldn't save. Try again.").

---

## 1A. Reusable layouts (closed set — every screen composes exactly one)

Owner rule: no hand-built pages. Every routed screen in the app — staff, member, public, auth,
kiosk, including the long tail covered in `research/ux-screens-longtail.md` — is **one shell +
one page layout with its slots filled**. A screen that does not fit a layout is a signal to fix
the screen, not to add a twelfth layout; adding one needs an owner decision. Layouts own geometry,
responsive behaviour, loading/error/empty switching, and focus/landmarks; screens own data and
copy. Layouts contain **zero** gating logic — callers pass already-filtered tabs/nav/actions.

### 1A.0 Shared slot types

```ts
type Action = { label: string; href?: string; onClick?: () => void; icon?: IconName;
  pending?: boolean; pendingLabel?: string; disabled?: boolean; disabledReason?: string; // required when disabled
  tone?: "default" | "danger"; external?: boolean; confirms?: boolean };              // confirms → label gets "…"
type SecondaryAction = Action | { label: string; menu: Action[] };
type Tab = { key: string; label: string; href: string; count?: number };              // gated tabs are omitted, never disabled
type Stat = { label: string; value: number | string; of?: number; progress?: number;   // 0–1
  tone?: "neutral" | "attention" | "danger" | "success"; href?: string };               // tone colours the number only
type CalloutProps = { size: "banner" | "panel" | "card" | "inline"; tone: "warn" | "danger" | "success";
  lead: string; body?: string; action?: Action };                                       // ≤1 per screen
type Identity = { kind: "date"; date: string } | { kind: "image"; src: string } |
  { kind: "icon"; icon: IconName; tone: Tone } | { kind: "avatar"; name: string; seed: string };
type QueryState = { status: "loading" | "error" | "ready"; error?: string; onRetry?: () => void };
type EmptyProps = { message: string; action?: Action };                                 // P17 dashed card
type PageHeaderProps = { eyebrow?: string; title: string; subtitle?: string; meta?: ReactNode;
  primary?: Action; secondary?: SecondaryAction; overflow?: Action[] };
```

Breakpoints used below: **375** (phone), **768** (tablet portrait), **1280** (desktop). Gutters
16 / 24 / 36. Content max-width 1120 (Inventory/Reports/Audit may opt into `wide` = full).

### L1. `AppShell` — sidebar + content (Yuyu Y1–Y10, Y16–Y17)

```ts
AppShell({
  variant: "staff" | "member";
  workspace: { name: string; subtitle: string /* role or membership status */; avatar: Identity;
    menu?: Action[]; locked?: boolean /* single-tenant: static card, no chevron */ };
  search?: { label: "Search and commands"; shortcut: "mod+k"; onOpen: () => void };
  nav: Array<{ label?: string /* section header; omit for flat */; caption?: string;
    items: Array<{ key: string; label: string; href: string; icon: IconName; badge?: number;
      badgeLabel?: string /* accessible-name suffix */; children?: Array<{ key; label; href }> }>;
    more?: Array<…same item shape…> }>;
  activeKey: string;
  pinned?: Array<SidebarSection>;          // bottom block: Settings family, Platform
  footerLinks?: Action[];                  // "View public page ↗"
  user: { name: string; role?: string; menu: Action[]; onSignOut: () => void };
  compactNav: "drawer" | "bottom-tabs";    // bottom-tabs only when ≤5 top-level items
  status?: ReactNode;                      // JobTray row
  children: ReactNode;                     // exactly one page layout (L2–L6)
})
```

| 375 | 768 | 1280 |
|---|---|---|
| 56 px top bar (menu, space name, search icon, avatar) **or** 64 px bottom tabs when `compactNav="bottom-tabs"`; drawer full-height 85 vw | same top bar; drawer 320 | fixed 264 sidebar, own scroll region between switcher and pinned block |

Used by: every staff tab (§2), the member area (S16). Not used by public, auth, kiosk.

### L2. `DashboardLayout` — greeting header + stat row + main + right rail (Y1, Y2)

```ts
DashboardLayout({
  header: PageHeaderProps & { eyebrow: string /* date or greeting */ };
  callout?: CalloutProps;
  progress?: ReactNode;                    // setup checklist card
  stats: Stat[];                           // renders ≤4; rest go to overflow
  overflowStats?: { label: "Everything else"; stats: Stat[] };
  main: Array<{ title: string; action?: Action; content: ReactNode /* ListRow[] */; empty: EmptyProps }>;
  rail?: { title: string; items: ActivityItem[]; seeAll?: Action } ;  // omit → main goes full width
  state: QueryState;
})
```

| 375 | 768 | 1280 |
|---|---|---|
| stats 2×2; rail below main, 3 items | stats 2×2 (4-up ≥900); rail below main | stats 4-up; main 1fr + rail 260, gap 28 |

Used by: staff Home (S1), member Home (S16), organizations home (governance-only), Platform dashboard.

### L3. `ListLayout` — header + callout + stats/tabs + filters + list/table + pagination (Y2, Y4)

```ts
ListLayout({
  header: PageHeaderProps;
  callout?: CalloutProps;
  stats?: Stat[];                          // ≤4, only when they summarise or act as filters
  tabs?: Tab[]; activeTab?: string;        // filter tabs with counts (P8)
  filters?: { search?: { label: string; value: string; onChange };
    controls?: ReactNode /* sort, saved views, column picker */; chips?: FilterChip[]; onClear?: () => void };
  body: { kind: "rows"; rows: ReactNode /* ListRow[] */ } | { kind: "table"; table: ReactNode /* DataTable */ };
  bulkBar?: { count: number; actions: Action[]; onClear: () => void };
  empty: EmptyProps; filteredEmpty?: EmptyProps;
  pagination?: { page: number; pageSize: number; count: number; onChange };
  rail?: ReactNode;                        // optional activity rail (Events)
  detail?: ReactNode;                      // a DetailLayout presentation="drawer"
  state: QueryState;
})
```

| 375 | 768 | 1280 |
|---|---|---|
| tabs scroll; filters collapse to search + "Filters" sheet; tables → stacked cards; bulk bar fixed bottom | tables keep ≤5 priority columns, rest via column picker | full table/rows; optional rail 260 |

Used by: Requests, Direct handout, Inventory, Members, Staff & roles, Events, Bookings, Machines index (rows→cards), Audit log, Inbox, Payments, Ledger, Transfers, Stocktake, To buy, Repair shelf, Containers, Categories, Warranties, Devices, Member cards, Accountability, Organizations, Organized events, Delivery log, Email templates, public events list (inside L9).

### L4. `DetailLayout` — back + identity + title/status/meta + actions + underline tabs + main/aside (Y7–Y10)

```ts
DetailLayout({
  presentation: "page" | "drawer";         // drawer: 640 (default) | 720 (wide); full-screen <768
  back: { label: string; href: string };   // "← All events"
  identity: Identity; title: string; status?: StatusPill; meta?: Array<string | ReactNode>;
  actions?: { primary?: Action & { targetsTab?: string } /* auto-hidden when targetsTab === activeTab */;
    secondary?: SecondaryAction; overflow?: Action[] };
  banner?: CalloutProps;                   // e.g. read-only/terminal state
  tabs?: Tab[]; activeTab?: string;        // URL-driven (?tab= or subpath)
  main: ReactNode; aside?: ReactNode;      // aside 280: "At a glance", CTA card
  footer?: { primary?: Action; secondary?: Action[] };   // sticky; drawers only
  danger?: DangerZoneProps[];              // rendered last in main
  state: QueryState;
})
```

| 375 | 768 | 1280 |
|---|---|---|
| identity 40, title 24; actions → full-width primary + ⋯; tabs scroll with fades; aside below main; drawer full-screen | aside below main; drawer full-screen | main 1fr + aside 280 gap 24; tab hairline full-bleed |

Used by: Request detail (drawer), Inventory item (drawer), Machine type page, Machine detail (drawer, wide), Event detail, Series detail, Bookable space, Member detail (drawer), Role detail, Report viewer (main = report, aside = report list on the left variant `asideSide="start"`).

### L5. `SettingsLayout` — sub-nav + sections of rows + sticky Discard/Save + DangerZone (Y5, Y6, Y16, Y17)

```ts
SettingsLayout({
  header: { title: string; subtitle: string /* scope + "Changes go live when you save." */ };
  tabs?: Tab[];                            // Profile | Security style (≤4)
  subnav?: "auto" | false;                 // auto when ≥5 sections: sticky list 200 (≥1280) / chip row (<1280), scroll-spy
  sections: Array<{ id: string; title?: string; description?: string;
    rows: Array<SettingsRowProps> | ReactNode;
    save?: { dirty: boolean; pending: boolean; error?: string; onDiscard: () => void; onSave: () => void } }>;
  danger?: DangerZoneProps[];
  state: QueryState;
})
SettingsRow({ label: string; helper?: string; control: ReactNode; status?: StatusPill;
  readOnly?: { reason: string }; action?: Action /* independent row action, e.g. "Update password" */ })
DangerZone({ title: string; consequence: string; action: Action & { confirms: true } })
```

| 375 | 768 | 1280 |
|---|---|---|
| rows stacked (label/helper above control); sub-nav = chip row; dirty save bar fixed bottom | rows split 220 / rest; chip-row sub-nav | rows split 300 / rest; sub-nav 200 sticky left |

Used by: Makerspace settings (S9), Account/MFA, member Account tab, Machine type › Settings tab content, item Details tab content (rows only), API access, Email settings, Modules, Usage & limits, Backup & restore, Data export, Platform settings, Evidence retention.

### L6. `FormPageLayout` — create/edit form + optional live preview (Y3, Y6 form card)

```ts
FormPageLayout({
  back?: { label: string; href: string };
  header: { title: string; subtitle?: string };
  form: ReactNode;                         // Field/Fieldset primitives; optional fields marked "Optional"
  preview?: { label: string /* "PUBLIC PAGE PREVIEW" */; content: ReactNode };
  submit: Action; cancel?: Action;         // "Create X" primary left + "Cancel" text
  width?: "default" | "narrow";            // narrow = 720 single column (tools)
})
```

| 375 | 768 | 1280 |
|---|---|---|
| single column; preview collapses into a "Preview" disclosure under the form; submit sticky bottom | preview below form | form 1fr + preview 300 gap 32 |

Used by: New event / New series, Add item, Create makerspace, New organization, Create bookable space, New API client, Add staff (full page variant), QR tools, staff Scanner, Bulk import, Email template editor.

### L7. `FlowLayout` — step rail + work panel + guarded footer (Y8/Y28 visual, SpaceWorks wizards)

```ts
FlowLayout({
  title: string; subject?: string;         // "Issue request #1042 · Meera Nair"
  steps: Array<{ key: string; label: string; state: "done" | "current" | "todo";
    summary?: string /* captured value, e.g. "BOX-0042" */; required?: boolean; missing?: boolean }>;
  current: string; onStepSelect?: (key: string) => void;   // only done steps selectable
  work: ReactNode;                         // camera block, evidence tile, item steppers
  footer: { back?: Action; next: Action };  // next.disabledReason mandatory when disabled
  onCancel: () => void; leaveGuard?: string;   // confirm copy when evidence captured
  result?: ResultCardProps;                // final step: tone, title, summary rows, actions; replaces work
  error?: CalloutProps;                    // partial-failure danger callout above footer
  compact?: boolean;                       // all steps on one scroll page (expert mode)
  presentation: "task" | "kiosk";          // task: hides sidebar; kiosk: rendered inside L11
})
```

| 375 | 768 | 1280 |
|---|---|---|
| full screen; rail → "Step 3 of 5 · Items" bar; camera full width; footer sticky | rail → top stepper; work full width | rail 300 + work panel; footer in work panel |

Used by: request issue/return (S3), direct handout (S4), job pickup (`HandoverConsole`), kiosk handover, offline replay correction, stocktake count session, tenant migration / backup restore wizards, create-makerspace onboarding.

### L8. `AuthLayout` (Y11) and `CenteredCardLayout` (Y12–Y15)

```ts
AuthLayout({
  brand: { headline: string /* the one accent phrase */; showcase?: ReactNode /* aria-hidden */;
    tenant?: TenantBranding /* member auth: tenant colour + logo */ };
  eyebrow?: string; title: string;          // "Welcome back."
  modeSwitch?: { options: [string, string]; value; onChange };   // Sign in | Create account
  social?: ReactNode; dividerLabel?: string; // "or with email"
  form: ReactNode; legal?: ReactNode;
})
CenteredCardLayout({
  media?: { icon: IconName; tone: Tone } | { avatars: [Identity, Identity] } | { banner: Tone };
  eyebrow?: string; title: string; body: ReactNode;   // names the identity in bold
  content?: ReactNode;                     // fields, code boxes, strength meter
  primary: Action; escape?: Action;        // one underlined escape link
  footer?: ReactNode;                      // "Signed in as … · Switch account"
  width?: 440 | 480;
})
```

| | 375 | 768 | 1280 |
|---|---|---|---|
| Auth | form only, 16 gutter; brand hidden | brand → 120 band above form | 50/50 split, form 400 wide |
| Centred | card becomes full-width sheet (no border), logo top | card 440 centred | card 440/480 centred |

Used by: staff sign-in, member sign-in/sign-up (Auth); reset password, verify email, MFA challenge, staff/organization invitation accept, change-password gate, access denied, "event not found" (Centred).

### L9. `PublicLayout` (Y18–Y25 chrome) and `PublicDetailLayout` (Y18, Y19, Y21, Y23)

```ts
PublicLayout({
  makerspace: { name: string; logo?: string; slug: string; branding?: TenantBranding };
  nav: Array<{ label: string; href: string }>;     // only modules that are on
  headerAction?: Action;                   // "Sign in" or the page primary when no action card
  liveStatus?: StatusPill;                 // "● Live · updates automatically"
  width: "wide" /*1110*/ | "default" /*960*/ | "narrow" /*600*/;
  breadcrumb?: Array<{ label: string; href?: string }>;
  aside?: ActionCardProps;                 // sticky right card (catalogue cart)
  children: ReactNode;
  footer: { credit: "Powered by space works"; links: Action[] };
})
PublicDetailLayout({                       // always rendered inside PublicLayout width="wide"
  cover?: { src: string; alt: "" };
  chips: Chip[]; title: string; tagline?: string;
  facts: Array<{ identity: Identity; primary: string; secondary?: string }>;  // date block, venue block
  sections: Array<{ id: string; label: string; content: ReactNode }>;         // anchor tabs
  actionCard: ActionCardProps;
  host?: { identity: Identity; name: string; href: string };
})
type ActionCardProps = { title: string; summary?: ReactNode /* counts + bar, avatars */;
  form?: ReactNode; primary?: Action; secondary?: Action[]; note?: string;
  state: "open" | "closed" | "done"; doneContent?: ReactNode;
  mobileBar: { summary: string; label: string } };
```

| 375 | 768 | 1280 |
|---|---|---|
| action card → sticky bottom bar opening a sheet; chips scroll; title 36 | action card below title block (static); title 48 | main 545–760 + sticky card 318–340 |

Used by: catalogue (PublicLayout + `aside`), item detail, public event, events list, programme, session, feedback (narrow), running order (narrow, `liveStatus`), ticket (narrow), public machines, public bookings, public stats, organization page, about/landing.

### L10. `KioskLayout` — full screen, large targets (Y27, Y28)

```ts
KioskLayout({
  context: { identity: Identity; title: string; subtitle: string };   // "Door check-in · Station 1"
  connection: { online: boolean; queued?: number };
  progress?: { done: number; of: number; label: string };            // "3 / 5 checked in"
  headerActions: Action[];                 // Full screen, Lock station
  mode: "lock" | "ready" | "work";
  lock?: { title: string; helper: string; pinLength: number; onSubmit: (pin: string) => void;
    pending: boolean; error?: string; disabledReason?: string };
  ready?: { primary: Action };             // "Start operator shift"
  work?: { capture: ReactNode /* camera */; panel: ReactNode /* result card or FlowLayout kiosk */;
    recent?: ReactNode };
  idleCountdown?: { seconds: number; onKeep: () => void };
  confirmLock?: { pendingCount: number; onDiscard: () => void; onKeep: () => void };
})
```

| 375 (phone door station) | 768 (portrait tablet) | 1280 (landscape tablet/desktop) |
|---|---|---|
| PIN: boxes above keypad, single column; work: camera 50 vh top, panel below | same stacked; keys 96×72 | PIN two-column; work: camera left 1fr + panel 1fr |

All targets ≥56 px, text ≥18, no hover-only affordances. Used by: kiosk handover station, event door check-in station, public desk kiosk, `ScannerPage` (standalone).

### 1A.11 Pattern → screen-type → layout map (shared with `ux-screens-longtail.md`)

| Screen type | Layout | Yuyu source | Patterns it composes | SpaceWorks screens (examples) |
|---|---|---|---|---|
| Dashboard home | L1 + **L2 DashboardLayout** | Y1, Y2 | P2 eyebrow header, P5 banner, P4 stats, P6 rows, P12 rail | Staff Home, member Home, organizations home, Platform dashboard |
| List + stats | L1 + **L3 ListLayout** | Y2, Y4 | P2, P5, P4, P8 tabs, P6 rows or P14/§5.1 table, P17 empty, P30 undo | Requests, Inventory, Members, Events, Bookings, Audit, Payments, every long-tail table tab |
| Detail with tabs | L1 + **L4 DetailLayout** (page or drawer) | Y7–Y10 | P3, P7, P4, P13 aside, P5 CTA card, P16 | Request, item, machine type, machine, event, series, space, member, role |
| Settings rows | L1 + **L5 SettingsLayout** | Y5, Y6, Y16, Y17 | P15, P16, P5 panel, P19, P24 | Makerspace settings, account, API access, modules, backups, exports |
| Create / tool form | L1 + **L6 FormPageLayout** | Y3, Y6 | P18 preview, P19 cards, P17 dropzone | New event/item/makerspace/space/client, QR tools, bulk import, template editor |
| Wizard / flow | **L7 FlowLayout** (task mode over L1, or inside L10) | Y8, Y28 (visual) | P21 camera, evidence tile (§5.2), P29 result card | Issue/return, direct handout, job pickup, stocktake session, restore/migration |
| Scanner / kiosk | **L10 KioskLayout** | Y27, Y28 | P28 PIN, P29 station, P30 undo, P5 panel | Kiosk station, door check-in, desk kiosk, scanner page |
| Public list | **L9 PublicLayout** | Y18 chrome, Y20 | P6 rows, P10 chips, P9 segmented | Catalogue (with `aside` cart), events list, machines, bookings |
| Public detail | L9 + **PublicDetailLayout** | Y18, Y19, Y21, Y23 | P25, P10, action card | Event page, item page, session, speaker, organization page |
| Public narrow task | L9 `width="narrow"` | Y24, Y25, Y26 | P26, P27 | Feedback, running order, ticket, self-checkout result |
| Auth | **L8 AuthLayout** | Y11 | P22, P9 | Staff sign-in, member sign-in/up |
| Centred task card | **L8 CenteredCardLayout** | Y12–Y15 | P23 | Reset, verify, MFA, invitations, access denied, not found |

---

## 2. Staff console sidebar IA

### 2.0 App-wide navigation rules (all shells)

These apply to every screen, including the long-tail tabs and pages in `ux-screens-longtail.md`:

1. **One navigation surface per shell.** Staff and member areas use `AppShell` (L1) with its
   sidebar; public pages use the `PublicLayout` header nav (only links for modules that are on);
   auth, centred-card and kiosk screens have **no** navigation beyond the logo and one escape link.
2. **Navigation is data, not markup.** Each shell's nav is built from an existing gating source
   (`moduleAllowedTabs` for staff, `memberTabs(modules)` for members, bootstrap `modules` for
   public) plus a presentation map. No screen adds its own nav, and no layout contains gating.
3. **Pages never repeat the sidebar.** In-page tabs (P3/P8) are for views of *one* object or
   filters of *one* list. A new top-level destination goes into the sidebar map, never into tabs.
4. **Sub-items appear only under the active parent** (Settings family, machine types, and in the
   member shell, none).
5. **≤5 destinations means bottom tabs on mobile** (handout-only console, member area with
   "More" as the fifth), otherwise a drawer.
6. **Counts in navigation are limited** to unread/needs-action badges (§2.3 rule 7). Everything
   else is counted on its page.
7. **Active state comes from the route,** with `aria-current="page"`, and the active item is
   always visible (auto-expand/scroll).
8. **Labels are nouns for places** ("Requests", "Items", "Payments") and verbs only for actions
   inside pages. The visible nav label may differ from the page `h1`, but the `h1` must contain
   the nav label's noun.

### 2.1 What exists

`ALL_TABS` in `frontend/src/features/staff/staffAccess.ts` holds **42 keys** (the brief said 41;
`platform-dashboard` and `usage` are the two most often forgotten). `TAB_GROUPS` sorts them into
9 groups shown as popovers in the floating `StaffDock`. Problems:

- "Operate" mixes the front desk (requests, direct, handover), money (payments), stock movement
  (ledger, transfers, stocktake) and procurement (tobuy).
- "Admin" holds 12 items of very different frequency.
- The three cross-venue tabs (organized, organization-analytics, organizations) are split across
  three groups even though they share one property: all are hidden in single-tenant mode and
  scoped beyond the selected makerspace.

**Unchanged:** keys, `TAB_PATHS`, `staffTabPath`, `getStaffAccess`, `filterTabsByEnabledModules`,
`moduleAllowedTabs`, the deny/redirect logic, `aria-label="Staff sections"`,
`aria-current="page"`, and the unread count in the accessible name. The sidebar is a pure
function of `moduleAllowedTabs`, a new `SIDEBAR_SECTIONS` presentation map, `TAB_LABELS` (or a
new `SIDEBAR_LABELS` override map) and `staffTabPath`. `TAB_GROUPS` stays for `CommandPalette` /
`SetupChecklist` until those are moved to the new map in the same commit.

### 2.2 Proposed sections (desktop ≥1024, 264 px sidebar)

Every one of the 42 keys appears exactly once. **Bold** = always visible within its section;
*italic* = inside that section's "More" disclosure (see the collapse rules in 2.3). Labels in
quotes are proposed display labels; the key and URL do not change.

| # | Section header | Items (key → label) | Notes |
|---|---|---|---|
| 0 | *(no header)* | **dashboard → "Home"**, **notifications → "Inbox"** (unread badge) | Yuyu "Home" pattern. The unread count stays in the accessible name ("Inbox, 3 unread"). |
| 1 | Front desk | **requests → "Requests"** (count badge: pending + ready), **direct → "Direct handout"**, **handover → "Job pickups"**, **payments → "Payments"** | The daily loop. Payments sits here because `record_payment` is a handout action and front-desk staff take money at the desk. |
| 2 | Inventory | **inventory → "Items"**, **needsfix → "Repair shelf"**, **stocktake → "Stocktake"**, **transfers → "Transfers"**, **tobuy → "To buy"**; *categories → "Categories"*, *containers → "Containers"*, *ledger → "Stock ledger"*, *warranty → "Warranties"*, *qr → "QR tools"*, *scanner → "Scanner"*, *bulk → "Bulk import"* | Page `h1` stays "Inventory" (the test pin is the panel heading, not the nav label). "Ledger" gains "Stock" so it is not mistaken for money. |
| 3 | Machines | **machines → "Machines"** + dynamic sub-items per machine type when active, **devices → "Devices"** | Sub-items come from the machine-type list already fetched by `MachinesPanel`, linked with `staffTabPath("machines", …, machineTypeSegment(type))`. This uses the existing `TABS_WITH_SUBPATHS` route, so it is the Yuyu "Settings › General" sub-nav pattern on an existing route. |
| 4 | Community | **members → "Members"**, **events → "Events"**, **bookings → "Bookings"**, *cards → "Member cards"* | |
| 5 | Insights | **reports → "Reports"**, **audit → "Audit log"**, *accountability → "Accountability"* | |
| 6 | Organizations | **organizations → "Organizations"**, **organized → "Organized events"**, **organization-analytics → "Org analytics"** | All three are cross-venue. The section shows a muted caption "Across venues" so the user knows the selected makerspace does not scope it. In single-tenant mode all three are hidden by gating, so the section disappears. For a governance-only actor this is the only section (see 2.5). |
| — | *(bottom block, above the user chip)* | **settings → "Settings"** with sub-items when any Settings-family tab is active: settings → "General", users → "Staff & roles", emailtemplates → "Email templates", email-logs → "Delivery log", api → "API access", exports → "Data export", backups → "Backup & restore", usage → "Usage & limits", modules → "Modules", migration → "Tenant migration" | Yuyu Settings › General / API access. "Admin" becomes one item that expands in place. If `settings` itself is not allowed but a child is (e.g. a role with only `edit_inventory` sees Email templates), the parent link goes to the **first allowed child**. |
| — | Platform *(bottom, superadmin only)* | **platform-dashboard → "Platform dashboard"**, **platform → "Platform settings"** | Rendered under a hairline with a muted "Platform" label so it is visibly a different scope. |

Item order inside a section is by frequency of use, not alphabetical.

### 2.3 Collapse and disclosure rules

1. A section header renders only if at least one of its items is allowed.
2. **A section with 4 or fewer visible items renders flat** with no "More". Most narrow roles hit
   this, e.g. a printing-only actor sees just "Warranties" in Inventory, flat.
3. A section with more than 4 visible items shows its **bold** items and a "More (n)" row
   (14 muted, chevron). Expanding is per-section and remembered per user in `localStorage`
   (wrapped in try/catch, a convenience only). **A section auto-expands when it contains the
   active tab**, so the active item is never hidden (this matches the unmounted-collapsed-content
   accessibility rule in PLAN §5).
4. Settings sub-items show only while a Settings-family tab is active (Yuyu rule); otherwise
   Settings is one row.
5. Machine-type sub-items show only while on `machines`, at most 8, then "All types →".
6. The sidebar body scrolls independently (`overflow-y:auto`) between the switcher and the
   bottom block. The active item is scrolled into view on route change.
7. **Counts in the sidebar are limited to two:** the Inbox unread count (existing) and the
   Requests "needs action" count (pending + ready-for-handover, from the already-cached
   dashboard query when the actor may read it; otherwise no badge). Badge: an 18 px tall pill,
   12 semibold, neutral tint. It becomes the accent tint when greater than 0 and is never red.
   Everything else gets its counts on its own page (P4 and P8).

### 2.4 Top and bottom of the sidebar

- **Top:** logo (horizontal lockup), then the **workspace switcher card** (makerspace tile, name,
  the role name from `activeRoleName` such as "Space Manager" or "Super Admin", and a chevron).
  The menu lists other makerspaces (searchable when there are more than 6), "Switch makerspace"
  for superadmin (today's `onSwitchMakerspace`), and "View public page ↗".
- Under the switcher: a full-width **search trigger** styled as an input ("Search or jump to…
  Ctrl K"). This *is* the `CommandPalette` trigger and keeps its accessible name "Search and
  commands" and its shortcut.
- **Bottom block:** "View public page ↗" (repeated for one-click access), then the **user chip**
  (initials, username, role). Its menu holds: "Account & two-step sign-in" (→ `/mfa`), Theme
  (Light / Dark / System segmented), and **"Sign out"** as a real `<button>` (test pin).
- `JobTray` (background jobs) attaches to the bottom block as a compact progress row when jobs
  are running, not as a floating tray.

### 2.5 Narrow consoles

**Handout-only (front desk, `handoutOnly === true`).** The allowed tabs are at most
`requests, direct, handover, payments, notifications`, all filtered further.

- **No section headers.** A flat list of 5 or fewer items in the order **Requests, Direct
  handout, Job pickups, Payments, Inbox.** No Home (they have no dashboard; `defaultTab` is
  Requests).
- The switcher card subtitle shows the role ("Front desk") and the base path stays
  `/guest-admin`.
- **Below 1024 px a bottom tab bar replaces the drawer** (5 or fewer items fit exactly: 64 tall,
  icon plus 12 px label, 44 px minimum targets, a safe-area inset). Front-desk staff work on
  tablets and phones at the counter, so one tap beats opening a drawer. The user chip moves into
  a top-bar avatar menu.
- The Requests page opens on the **Ready** tab for this actor (they cannot review, and the
  pending query is already disabled for `guestOnly`).
- Optional, product decision: a persistent "Scan box" button in the top bar that opens the QR
  scanner and jumps to the matching ready request. This needs a box-to-request lookup and is a
  behaviour addition, so it is out of scope unless approved.

**Governance-only** (`allowedTabs = ["organizations"]`): sidebar = Organizations only, and no
switcher menu entries other than "View public page" (there is no makerspace scope). The page uses
the Yuyu home pattern Y1 ("Your organizations" cards).

**Machine-only** (`isMachineOnly`): typically Home, Inbox, Machines (with type sub-items),
Warranties, Reports, Email templates. Rule 2 keeps it flat. The machine-type sub-items become the
main navigation, which is exactly what the scoped operator needs.

### 2.6 Below 1024 px (non-handout)

A slim top bar (56 tall): hamburger (opens the sidebar as an off-canvas drawer, focus-trapped,
Esc closes), the makerspace name, a search icon (palette), and the user avatar. The page title
lives in the page, not the bar. The drawer reuses the same sidebar component.

---

## 3. Screen-by-screen spec

Conventions for every staff screen: the app shell from §2, a 36 px gutter, content max-width
1120 (wider pages such as Inventory and Reports may go full width), and a `PageHeader` from P2 or
P3. "Primary" means the single filled button. States: **Loading** = skeleton in the final layout
shape (never "Loading…" text alone); **Error** = an inline error block in place of the content
region with "Couldn't load X. Try again." and a Retry button; **Empty** = P17 dashed card.

Mobile defaults (<768): stat grids become 2 columns; the activity rail drops below the main
column, limited to 3 items with "See all"; row cards keep the chip and stack the right slot under
the meta; header actions collapse to the primary plus an overflow "⋯"; underline tabs scroll
horizontally with the active tab scrolled into view; drawers open full screen.

### S1. Staff Home / Dashboard (`dashboard`) ← Y1 + Y2

**Layout:** L1 `AppShell` + L2 `DashboardLayout`. The slots are filled as follows:
`header` = date eyebrow, "Dashboard" `h1` (greeting as eyebrow), Quick add primary;
`callout` = the top-severity alert; `progress` = SetupChecklist; `stats` = the top 4 tiles;
`overflowStats` = the remaining tiles; `main` = [Coming up]; `rail` = audit or notifications
activity.

```
Wednesday, 14 October
Good morning, Priya                                   ( View public page ↗ ) [■ + Quick add ▾]
┌ ! 3 loans are overdue. Remind borrowers or record a return.        Review overdue → ┐  (only if >0)
└─────────────────────────────────────────────────────────────────────────────────────┘
┌Pending requests┐┌Ready for handover┐┌Overdue loans┐┌Bookings to approve┐   ← max 4 "needs action"
│ 4              ││ 2                ││ 3           ││ 1                 │
└────────────────┘└──────────────────┘└─────────────┘└───────────────────┘
Coming up                                                     Recent activity
┌OCT┐ Meera Nair returns 3 items        Due tomorrow (Remind)   (PO) Priya accepted request
│15 │ Request #1042 · Arduino kit ×2…                              #1042 · 2 min ago
┌OCT┐ Laser cutter induction            12 / 16 going           (DP) Dev returned Multimeter
│16 │ Event · 6:30 PM · Main hall                                  · 1 hr ago
┌OCT┐ Woodshop bench booked              Awaiting approval         …
│17 │ Booking · 10:00–12:00 · Sana Khan        (Review)           See all activity →
Everything else ▸  (disclosure: remaining non-zero tiles as a compact 2-col list)
[ Setup checklist card — only while incomplete, above "Coming up" ]
```

- **Data:** the existing `/admin/makerspace/{id}/dashboard` counts. "Coming up" merges three
  existing endpoints: active loans ordered `return_due_at` (next 5 due), upcoming events
  (`useEvents`, if the module and permission allow) and pending/upcoming bookings. Activity
  comes from `/admin/audit-logs?makerspace=…` (page size 6) when `canViewAudit`, otherwise from
  the notification inbox, otherwise the rail is hidden and the main column goes full width.
- **Stat cards:** pick **up to 4** tiles by priority: those with `actionNeeded && value>0` first
  (danger tones, then warn), then fill with in-flight counts. All other permitted tiles move to
  the "Everything else" disclosure. This keeps all 17 reachable without the current wall of
  tiles. Each card is a link (existing `dashboardHref`). The tone shows on the **number**, never
  as a fill (aligns with the current `rest` style).
- **Callout:** at most one, chosen by severity: overdue loans, then failed emails, then problem
  reports, then maintenance overdue. It has an action link.
- **Primary:** "Quick add" with a menu of the existing `useQuickCreate` targets (item, event,
  booking) the actor can use. If only one is permitted it becomes a direct button. If none, no
  primary.
- `SetupChecklist` becomes a progress card ("Set up Space Works · 4 of 7 done", a bar, the next
  step as a link) placed above "Coming up". It is dismissible once complete.
- **Empty:** "Nothing needs you right now. New requests and due-backs will show up here."
  **Loading:** 4 card skeletons plus 3 row skeletons. **Machine scope** (`scope_mode:"machine"`):
  the cards use machine tiles and "Coming up" shows maintenance due and prints ready.
- The panel heading "Dashboard" is a test pin. Keep an `h1` with the visible text "Dashboard" and
  the greeting as the eyebrow, **or** update the pin deliberately in Phase 4. Recommendation:
  `h1` "Dashboard" with the greeting above it.

### S2. Requests list (`requests`) ← Y2 (tabs + rows) + Y8 (inline actions)

**Layout:** L3 `ListLayout`. The slots are filled as follows: `header` = "Requests", with the
subtitle and a conditional primary; `tabs` = Pending / Ready / On loan / History with counts;
`filters` = search plus sort and saved views; `body` = rows (`ListRow` with date/avatar chip and
an inline next step); `empty`/`filteredEmpty` per tab; `pagination` per queue; `detail` = S3
drawer.

```
Requests                                                   ( Export ) [■ Start handover ]*
Borrow requests from members, from review to return.
Pending 4 │ Ready 2 │ On loan 7 │ History                 [ Search name, email, purpose  ⌕ ] [Sort ▾] [Views ▾]
━━━━━━━━━
┌ (MN) Meera Nair                              ⏱ Requested 2 h ago     (Pending)   [ Review ] ⋯ ┐
│      #1042 · 3 items · Arduino kit ×2, Multimeter ×1 · "Robotics club demo"                │
└─────────────────────────────────────────────────────────────────────────────────────────────┘
┌OCT┐ Dev Patel   (Ready tab)                   Box not assigned yet    [■ Start handover ] ⋯ ┐
│15 │ #1039 · 1 item · Soldering station · due back 22 Oct                                      │
┌OCT┐ Sana Khan   (On loan tab; chip = due date, band red if overdue)  Overdue 2 days  [ Return ] ⋯
```
\* The header primary is shown only on the Ready tab, and only when exactly one request is ready
(it opens it). Otherwise there is no header primary and the per-row action carries it.

- **Tabs** (P8) map to the existing queries: Pending = `pending-requests` (hidden for
  `guestOnly`), Ready = `accepted-requests`, On loan = `active-loans`, History = `request-history`.
  Counts come from each query's `count`. The three live queries already run together today, so
  showing their counts is free; History shows no count. URL: extend the existing `queue` list-state
  value to `pending|accepted|active|history` (frontend only). The default tab is the first
  non-empty of Ready (handout-only) or Pending (others).
- **Row (P6 adapted):** chip = requester avatar on Pending, due-date chip on Ready and On loan
  (red band and "Overdue n days" when past due; the word is always present). Title = requester.
  Meta = `#id · n items · first two items · "purpose"` with a "+n more" overflow. Status pill.
  **One inline next step:** Pending → "Review" (opens detail; Accept/Reject live there),
  Ready → "Start handover" (guided wizard), On loan → "Return" (guided return). Shelf location
  shows in the detail only (staff-only, but it adds noise to the row).
- **"⋯" row menu:** Set due date, Renew (when `loans.renewals`), View timeline (when
  `canViewAudit`), View issue/return photo(s), Copy link.
- The StatusStepper moves out of the row into the detail drawer (rows stay 82 tall).
- **Empty per tab:** Pending: "No requests waiting for review." Ready: "Nothing to hand over. Accepted
  requests land here." On loan: "Nothing is out on loan." History: "Returned and closed requests
  will appear here."
- **Search empty:** "No requests match "x". Clear search" (link).
- **Error:** inline block per tab with Retry. **Loading:** 4 row skeletons (`RequestListSkeleton`
  restyled).
- **Mobile:** rows stack; the inline action becomes a full-width button at the bottom of the
  card (44 tall).

### S3. Request detail + issue/return flow ← Y7 (detail header, at-a-glance) + Y8/Y28 (scan workspace)

**Layout:** the detail is L4 `DetailLayout presentation="drawer"`. The slots are filled as
follows: `back` = Requests; `identity` = requester avatar; `title` = "Request #id"; `status`;
`meta`; `tabs` = Overview / Evidence / Timeline; `main` = items plus stepper; `aside` = At a
glance; `footer` = the status-driven primary. The handover is L7 `FlowLayout
presentation="task"` with 5 steps; `work` = camera, borrower card, item steppers or evidence tile;
`result` = the success card.

**Detail** opens as a 640 px right drawer over the list, deep-linkable with `?request=<id>`
(new param, like Events' `?event=`). Full screen on mobile.

```
← Requests                                                             ✕
(MN)  Request #1042                          (Ready for handover)
      Meera Nair · requested 14 Oct, 9:12 · due back 22 Oct
○──●──○──○  Requested · Accepted · Issued · Returned            (StatusStepper)
Overview  Evidence  Timeline
──────────────────────────────────────────────────
Items                                        At a glance
┌ Arduino kit        ×2   Shelf B3  (QR-tracked) ┐   Purpose   Robotics club demo
│ Multimeter         ×1   Shelf A1               │   Contact   meera@… · +91…
└────────────────────────────────────────────────┘   Box       Not assigned
                                                     Accepted  by Priya (Space Manager)
─────────────────────────────────── sticky footer ─────────────────────
( Set due date )                                  [■ Start handover ]
```

- **Footer primary by status:** pending → "Accept…" (opens the accept-quantities modal; Reject
  as an outline secondary; Set due in "⋯"); accepted → "Start handover"; issued or
  partially_returned → "Record return"; terminal → none.
- **Evidence tab:** issue and return photos as thumbnails loaded on demand through the existing
  signed-URL fetch, labelled with type, actor and time, never as public URLs. Empty: "No
  photos yet. The issue photo is taken during handover."
- **Timeline tab:** `RequestTimelineBlock` as an activity list (P12 style) when `canViewAudit`.
- Damaged, missing and to-fix outcomes show as a danger-tinted advisory under Items.

**Handover flow** (`HandoverWizard`, issue and return). One component for both. It replaces the
side-by-side "Assign + issue" modal and "Guided issue" button, which are two buttons for one job.
The non-guided `AssignIssueModal` / `ReturnRequestModal` / `IssueDialog` / `ReturnDialog` become
a "Compact view" toggle of the same flow (all steps on one scroll page) for experienced staff.
**Hard rules are unchanged:** box QR, borrower check, items and assets, an issue photo
(mandatory), a return photo plus a remark (mandatory), the kit checklist and the receipt.

```
Desktop: full-screen task mode (no sidebar), 2 columns
┌ Issue request #1042 · Meera Nair ─────────────────────────────── ( Cancel ) ┐
│ ① Scan box        ✓ BOX-0042   │                                            │
│ ② Check borrower  ✓            │   ┌──────── camera (dark, r16) ────────┐   │
│ ③ Items           2 / 3 assets │   │        ⌜            ⌝              │   │
│ ④ Photo & remark  ● required   │   │   Hold the asset QR in the frame   │   │
│ ⑤ Receipt                      │   └────────────────────────────────────┘   │
│                                │   Can't scan? [ Type the QR code   ] (Check)│
│                                │   Scanned  ✓ ARD-0091  ✓ ARD-0092   Remove  │
│                                │                         ( Back ) [■ Next ]  │
└────────────────────────────────┴────────────────────────────────────────────┘
```

- **Left rail:** 5 steps with state (done ✓ plus its captured value, current ●, locked). Done
  steps are clickable to go back. Mobile: the rail becomes a top progress bar with "Step 3 of 5 ·
  Items" and the camera fills the width.
- **Step 1 Scan box:** the camera block (P21 and P29) **starts on entry** because scanning is
  the task. Manual entry sits beneath it. A success shows the box label inline with a green check
  and auto-advances after 600 ms (an announced `role=status`).
- **Step 2 Borrower:** an identity card (avatar, name, membership status pill, waiver status),
  the optional member-card scan (`ScanCardBox`), and the confirmation checkbox "I checked the
  borrower against this request" (keep the wording; it is the accountability statement).
- **Step 3 Items:** issue mode shows an asset counter as a progress stat ("Assets scanned 2 / 3")
  with continuous scanning in the same camera block and the scanned list with Remove. Return
  mode shows per-item rows with three steppers (Returned / Damaged / Missing) and a live "of n
  remaining" check (reuse `QuantityInput` validation copy).
- **Step 4 Photo & remark:** the **evidence tile** (see §5) is large (16:9 placeholder, "Take
  photo" primary, "Upload from device" link). After upload it shows the thumbnail, "Photo #182
  attached" and "Retake". The remark field is labelled "Return remark" with a "Required" chip in
  return mode and "Remark · Optional" in issue mode. The kit checklist follows. The step footer
  primary reads **"Confirm issue"** / **"Confirm return"** and is disabled with the reason
  ("Add the return photo and a remark to continue."), never silently disabled.
- **Step 5 Receipt:** a full-panel **success result** (P29 green card): "Issued to Meera Nair",
  the summary (box, items, photo #, time), "Print receipt" (outline) and "Done" (primary). **No
  Undo.** Handover records are immutable and audited, so the summary-before-confirm in step 4 is
  the safety net.
- **Partial-failure copy** is kept verbatim in intent ("Box assigned, but issue failed: … The
  request still needs the issue step; retry with the assigned box.") and shown as a danger
  callout above the footer.
- **Escape:** "Cancel" is disabled while saving. Closing with captured evidence asks "Leave
  handover? The uploaded photo stays unattached and will be cleaned up." **Copy needs owner
  sign-off:** the abandoned-upload cleanup is default-off, so the claim must match the
  deployment.

### S4. Direct handout (`direct`) ← Y2 list + S3 flow

**Layout:** L3 `ListLayout`. The slots are filled as follows: `header` = "+ New handout"
primary; `tabs` = On loan / Returned / Claim codes; `body` = rows with inline Return. New handout
and Return are L7 `FlowLayout` (4 and 3 steps).

```
Direct handout                                                    [■ + New handout ]
Lend tools straight from the shelf, without a request.
On loan 5 │ Returned │ Claim codes
┌OCT┐ Arjun Rao                                       Due 20 Oct     [ Return ] ⋯
│20 │ Handout #88 · Multimeter, Probe set · 2 tool QRs · by Priya
```

- "+ New handout" opens the guided `DirectHandoverWizard` in task mode (borrower card, then
  tools, then photo, then receipt; the same shell as S3). The always-visible inline issue form
  currently on the page moves into that flow's "Compact view". The page itself becomes the
  **list of direct loans** with inline Return (the existing `DirectLoanReturnModal` restyled as
  the S3 return steps).
- The "Claim codes" tab hosts `MemberClaimCodes`.
- **Empty:** "No tools are out on direct handout. Start one with New handout above."
- **Mobile:** the primary becomes a full-width sticky bottom button above the bottom tab bar
  (handout console).

### S5. Inventory list (`inventory`) ← Y2 header/stat cards + adapted dense table (§5)

**Layout:** L3 `ListLayout width="wide"`. The slots are filled as follows: `header` = title,
meta counts, "+ Add item" primary, an Export menu as secondary; `callout` = reorder suggestions;
`tabs` = All / Low / Out / Archived; `filters` = search, saved views and column picker; `body` =
table (`DataTable` in card chrome); `bulkBar` = QR enable/disable and export; `detail` = S6
drawer.

```
Inventory                                                 ( Export ▾ ) [■ + Add item ]
248 items · 12 low stock · 3 on the repair shelf
┌ ! 6 items are at or below their reorder point.                       Review suggestions → ┐ (only if >0)
All 248 │ Low stock 12 │ Out of stock 4 │ Archived            [ Search items ⌕ ] [Views ▾] [Columns ▾]
┌──────────────────────────────────────────────────────────────────────────────────────────────┐
│ ☐  Item                          Mode         Total  Available     Issued  Damaged  Lost   ⋯ │ 40h header
│ ☐  [img] Arduino Uno R3          Count        20     (Limited) 3   15      1        1      ⋯ │ 56h rows
│ ☐  [img] Multimeter Fluke 101    Individual   6      (Available) 5 1       0        0      ⋯ │
└──────────────────────────────────────────────────────────────────────────────────────────────┘
                                             1–24 of 248   ‹ 1 2 3 … 11 ›
╭ 3 selected   ( Enable QR ) ( Disable QR ) ( Export 3 )                     Clear ╮  ← sticky bulk bar
```

- **Collapse the ~9 toolbar buttons** to: primary "+ Add item"; secondary "Export ▾" (CSV/XLSX,
  scoped to the selection when rows are selected); filter **tabs** for Active/Low/Out/Archived
  (replacing three toggles; the `archived`, `low_stock` and `out_of_stock` URL params are
  unchanged); Saved views and a column picker on the right. Bulk QR enable/disable lives **only**
  in the selection bar (the existing `BulkActionToolbar`).
- **Row:** the whole name cell opens the item detail. The row "⋯" menu holds Edit, Move to repair
  shelf…, Add to To buy…, Archive. **Archive has no confirm dialog** because it already has a
  toast with Undo (`useInventoryArchive`): "Arduino Uno archived. Undo". Restore works the same
  way.
- The availability cell keeps `InventoryAvailability` as a status pill with the word.
- `ReorderSuggestions` becomes the single callout (P5.1) linking to a drawer with the suggestions.
- **Empty (no items):** "No parts added yet. Add your first item." with "+ Add item" repeated
  in-card (brand voice example). **Filtered empty:** "Nothing low on stock." / "No archived
  items."
- **Mobile:** table becomes stacked cards (image, name, availability pill, "Issued 15 · Damaged
  1 · Lost 1"), selection via long-press or a checkbox; bulk bar fixed at the bottom.

### S6. Inventory item detail ← Y7 (detail header + tabs) + Y5 (settings rows, danger zone)

**Layout:** L4 `DetailLayout presentation="drawer" width=720`. The slots are filled as follows:
`identity` = image; `status` = availability; `tabs` = Details / Stock / QR & assets / History /
Custody; Details `main` = `SettingsRow`s (the rows from L5, used standalone) with a dirty save
footer; `danger` = Archive. Add item is L6 `FormPageLayout`; `preview` = the public
`ProductCard`.

Opens as a drawer at 720 px or full screen on mobile (it is currently the `ItemModal` with 8
stacked blocks). Deep link `?item=<id>` (new param; the current `id` list filter stays separate).

```
← Inventory
[img] Arduino Uno R3                                 ( View public page ↗ )
      (Limited) Count-tracked · Electronics · Public: status only
Details  Stock  QR & assets  History  Custody
───────────────────────────────────────────────
Details: settings rows (Name & description │ Photo │ Category │ Public visibility │ Kit components │ Borrowing terms)
                                              ( Discard ) [■ Save changes ]   ← appears when dirty
┌ Archive item ─ Hides it from active inventory and the public catalogue. ( Archive… ) ┐ red
```

- **Stock tab:** stat cards (Total, Available, Issued, Damaged, Lost), then `QuantityAdjust` as a
  form card with a reason; Individual mode adds the asset table (`IndividualAssets`).
- **QR & assets:** `QrHistory`. **History:** `LendingHistory`. **Custody:** `ChainOfCustodyBlock`.
  The last two only when `canViewAudit`.
- **Public visibility row** groups `is_public`, `public_availability_mode` (segmented: Exact
  count / Status only / Hidden) and `show_public_count`, with a **live preview pill** of what the
  public sees (Y3 live-preview pattern). The rule from CLAUDE.md is computed client-side only for
  display. "Exact count" with `show_public_count=false` previews as "Limited" and the helper says
  why.
- **Add item** uses the same layout as a create page (Y3): form left, "Public catalogue preview"
  card right (ProductCard rendering). Then, as today, it reopens in edit mode to add a photo, with
  the copy "Item created. Add a photo so members can recognise it."

### S7. Members (`members`) ← Y4

**Layout:** L3 `ListLayout`. The slots are filled as follows: `header` = "Invite member" primary;
`callout` = pending requests; `tabs` = Members / Requests / Present now / Plans / Waivers;
`body` = table; `detail` = member drawer (L4 drawer with `SettingsRow`s).

```
Members                                                         [■ Invite member ]
People who belong to this makerspace and what they can do here.
┌ ! 3 people are waiting for approval.                                   Review requests → ┐
Members 128 │ Requests 3 │ Present now 4 │ Plans │ Waivers          [ Search ⌕ ] [Status ▾]
┌──────────────────────────────────────────────────────────────────────────────────────┐
│ Person                        Role             Status        Waiver      Joined    ⋯ │
│ (MN) Meera Nair  (Verified)   (Member)         (Active)      Current     13 Oct    ⋯ │
│      meera@example.test                                                              │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

- **Invite** = the Y4 invite card pattern, opened from the primary into a modal: email, role
  select (defaults to first role, as today) and "Send invite". The Requests tab lists both
  membership requests and staff invitations (today's second panel), each with inline
  "Approve" (primary pill) and "Decline…" (red text). The plan picker appears inline in the
  approve modal when `membership` is on.
- **Row "⋯":** Change role, Verify / Unverify, Can refer (toggle), Can verify (toggle), Terms,
  Record witnessed acceptance (only when the waiver is needed), then a divider, then
  "Revoke membership…" (red). Clicking the row opens a **member drawer** with settings rows
  (role, capabilities, waiver, payments via `PaymentReconcileActions`, vouches) so the table
  row stays one line.
- **Present now tab** = the current "Currently present" panel as a P14 table with "until 18:30".
  The Plans and Waivers tabs show only when `membership` is on and `canManageMakerspace` (current
  gating).
- **Empty (members):** "It's just you so far. Invite someone with the button above." **Requests
  empty:** "No one is waiting. New membership requests appear here."
- **Mobile:** the table becomes cards (name, role and status pills, ⋯).

### S8. Staff & roles (`users`) ← Y4 (table) + Y6 (checkbox cards for permissions)

**Layout:** L3 `ListLayout`. The slots are filled as follows: `tabs` = Staff / Roles /
Invitations; `body` = table. The role detail is L4 `DetailLayout` (page). Its `main` =
permission checkbox-card groups with a Discard/Save footer, and `danger` = "Delete role…".
"Create makerspace" is L6 (or an L7 onboarding flow).

```
Staff & roles                                   ( Create makerspace )* [■ Add staff ]
Who can work in this makerspace and what each role is allowed to do.
[Makerspace ▾]*  Staff 9 │ Roles 6 │ Invitations 1
Staff table: Person · Role (pill) · Makerspace* · Status (Restricted pill if any) · ⋯ (Change role, Reset password…, Restrict…, Restore, Revoke role…)
```
\* superadmin / multi-makerspace only.

- The first-staff invitation link renders as the **Y4 invite-link card** (read-only field,
  "Unused" pill, "Copy link" primary, "Dismiss").
- **Roles tab:** role list rows (name, the "Default" pill for the 4 protected roles, "n actions",
  "m staff") leading to a role detail with the `RoleEditor` actions grouped as **checkbox cards**
  (Y6) by area (Lending, Inventory, Machines, Community, Money, Admin), each card showing the
  human label plus the action key in mono, and `RoleMachineScopeEditor` as its own settings row.
  Save via a Discard/Save pair. Danger zone: "Delete role…" for custom roles.
- **Invitations tab:** `StaffInvitations` (when `staff.invitations`).
- **Empty:** "No staff yet. Add staff to share the work."

### S9. Makerspace settings (`settings`) ← Y5 + Y6 + Y17

**Layout:** L5 `SettingsLayout subnav="auto"`. The slots are filled as follows: `sections` = the
12 groups in the table below, each with its own `save`; `danger` = the archive request. The
Settings-family siblings (Staff & roles, API access, and the rest) are separate tabs using L3 or
L5 as listed in S24.

`MakerspaceSettingsPanel` stacks ~30 independent sections on one page. Spec: **an in-page
sub-nav** (sticky, left column 200 at ≥1280; a horizontal scroll chip row below that) with
scroll-spy, so no routing change is needed. Optional later: `settings/<section>` via
`TABS_WITH_SUBPATHS`, which PLAN §5 already allows.

| Sub-nav section | Existing components |
|---|---|
| General | `MakerspaceGeneralSettings`, `MakerspaceProfileSettings`, `MakerspaceLocationSettings` (incl. hours) |
| Branding & public site | `MakerspaceBrandingSettings`, `MakerspacePublicStatsSettings`, public print status lookup policy, `MakerspaceSubdomainSettings`, `MakerspaceCustomDomainSettings` |
| Features | `MakerspaceFeatureSettings`, `SpacePacksPanel` |
| Lending | loan, reminder and kit settings inside `MakerspaceReminderSettings`, `KioskStationSettings` |
| Membership | `MakerspaceMembershipSettings`, `MakerspaceGeofenceSettings` |
| Bookings | `MakerspaceBookingSettings`, `MakerspaceBookingRulesSettings` |
| Machines & materials | `MakerspaceFilamentSettings` |
| Money | `MakerspacePaymentSettings`, `BillingDocumentsSettings` |
| Notifications | staff email toggle, `NotificationTimingSettings`, `NotificationMuteMatrix`, `NotificationRecipientPicker`, `NotificationDestinations` |
| Email & integrations | `MakerspaceEmailSettings`, `MakerspaceWebhookSettings`, `IntegrationHealthPanel` |
| Privacy & evidence | Superadmin access, `EvidenceRetentionPanel` (and `AbandonedUploadCleanupSection` where it lives) |
| Danger zone | `MakerspaceArchiveRequestPanel` (the two-key archive request) as a P16 card |

- Every section is a P15 block: an `h2` section title (20 bold), then rows with label and helper
  on the left and the control on the right.
- **Save model:** instant toggles keep saving on change, with a toast "Staff emails turned off."
  and, where the PATCH is symmetric, Undo by re-PATCHing the previous value. Text and field
  groups get a **per-section Discard/Save pair that appears only when the section is dirty**
  (sticky at the bottom of the viewport while that section is in view). Never one global Save
  for 30 sections.
- **Status pills on rows** (On/Off, "Token only") stay; the button copy is the action ("Turn off
  access").
- The "Manage my authenticator…" link moves to the user menu (§2.4); it is personal, not
  makerspace configuration.
- The `h1` "Makerspace settings" is a test pin and is kept. The sidebar item reads "General".
- **Loading:** row skeletons per section. **Error:** per-section error with Retry (the sections
  load independently).

### S10. Machines ← Y1 cards (index), Y7 detail header + tabs (type page), Y5 rows (machine detail)

**Layout:** the index is L3 `ListLayout`. The slots are filled as follows: `body` = rows,
rendered as a card grid via the `ListRow` card variant; `callout` = overdue maintenance. The type
page is L4 `DetailLayout` (page, `identity` = type icon). Its `tabs` = Machines / Service queue /
Consumables / Certifications / Settings, with Machines-tab `main` = an embedded table and status
filter tabs. The machine detail is L4 `DetailLayout presentation="drawer" width=720`, with
`danger` = Retire.

**Index** (`/admin/machines`):

```
Machines                                                    [■ + Add machine type ]*
24 machines across 5 types · 3 running · 1 in maintenance
┌ ! Maintenance is overdue on 2 machines.                           Review → ┐ (only if >0)
┌[🖨] 3D printers ─────────┐ ┌[⚡] Laser cutters ───────┐ ┌ + Add machine type ┄┄┐ (dashed, if allowed)
│ 8 machines · 3 running    │ │ 2 machines · idle        │
│ 4 jobs in queue  (Review) │ │ Next maintenance 3 Nov   │
└───────────────────────────┘ └──────────────────────────┘
Type settings ▸ (MachineTypesPanel, shared consumables, delegated recipients) — disclosure
```
\* when `canConfigureMachineTypes`.

**Type page** (`/admin/machines/12-3d-printers`, an existing subpath):

```
← All machine types
[🖨] 3D printers                                    ( Public page ↗ ) [■ + Add machine ]
     8 machines · 3 running · 1 maintenance
Machines 8 │ Service queue 4 │ Consumables │ Certifications │ Settings
Machines tab: table rows [img] Name / model · location | (Running) pill | 312 h | ⋯   + status filter tabs (All · Idle · Running · Reserved · Maintenance · Offline)
```

- Map the stacked sections to tabs: Machines (list plus `MachineCreateForm` moved into the
  "+ Add machine" modal), Service queue (`PrinterServiceConsole` / `MachineServiceConsole`),
  Consumables (the pool form and list), Certifications (`CertificationsPanel`), Settings
  (`MaterialCataloguePanel`, `MachineReminderPolicy`). The tab state uses a query param
  `?view=` (frontend only). Tabs show only when their gate holds today.
- **Machine detail** (`MachineDrawer`, 720 px drawer):

```
[img] Prusa MK4 #2                         (Running) · 3D printer · 312 h total
      [■ Mark idle ]  ( Log maintenance )   ⋯ (Retire…)
Overview  Operators  Consumables  Usage  Maintenance  Documents  Errors  Warranty
Overview: stat cards (Usage hours · Jobs this month · Next maintenance · Open errors), then settings rows (photo, details, public detail)
┌ Retire machine ─ Takes it out of service and off the public page. ( Retire… ) ┐ (danger, can_retire)
```

- Replace the button-styled tablist with P3 underline tabs (keep `role=tablist` and wrapping, so
  every tab stays visible; the current comment about clipping still applies). The header primary
  is the most common status transition the actor may perform (from `OverviewTab`'s status
  block).
- **Empty:** "No machines are registered for this type. Add the first one with Add machine."
  Keep the "requires a successful load" rule from `MachineTypePage`.

### S11. Events list (`events`) ← Y2 exactly

**Layout:** L3 `ListLayout`. The slots are filled as follows: `header` = greeting eyebrow, "New
series" secondary, "+ New event" primary; `callout` = collaboration invites or door-ready;
`stats` = 4; `tabs` = Upcoming / Drafts / Past / Series; `body` = date-chip rows; `rail` = recent
registrations (when data exists). New event and New series are L6 `FormPageLayout`, with
`preview` = the public event card.

```
Good morning, Priya
Events                                                   ( New series ) [■ + New event ]
┌ ! Laser workshop is tomorrow. Download the guest list for offline check-in.  Prepare check-in → ┐
┌Upcoming 3┐┌Going 46┐┌Awaiting approval 2┐┌Drafts 1┐
Upcoming │ Drafts 1 │ Past │ Series 2                              Recent registrations
date-chip rows: right slot = "12 / 30 going" bar │ "Finish & publish" pill │ "No guests yet · Share"
```

- **Remove the always-open create form** from the list page. "+ New event" opens a create page
  (Y3 layout: form left, public event card preview right) and "New series" opens the series
  variant. The `useQuickCreate("event")` hook opens the same page.
- `CollaborationInbox` and `EventSeriesCollaborationInbox` collapse into **one callout** when
  invitations are pending ("2 venues invited you to co-host. Review →") that opens a drawer. No
  callout when empty.
- **Stat cards** use `registration_counts` summed over the loaded page only if the backend has no
  aggregate. **Flag:** prefer a server count; otherwise show only Upcoming and Drafts (exact from
  list counts) and omit the rest rather than show page-local sums.
- **Rail:** latest registrations if an endpoint exists; otherwise hide the rail.
- The table becomes date-chip rows. Status words: Draft (grey, dashed row), Published (green),
  Cancelled (red word pill), Completed (grey).
- **Empty (no events):** dashed "+ New event" placeholder row: "Your events will appear here."

### S12. Event detail ← Y7, Y8, Y9, Y10

**Layout:** L4 `DetailLayout` (page). The slots are filled as follows: `identity` = date chip;
`actions.primary` = status-driven (with `targetsTab="checkin"` so it hides on that tab); `tabs` =
the 7 tabs below; Overview `aside` = At a glance plus the CTA card; Settings tab `main` =
`SettingsRow`s; `danger` = Cancel event. The series detail uses the same layout with an icon
identity.

`EventDrawer` becomes a full detail page reached by `?event=<id>` (the param already exists). It
is too dense for a drawer: 9 stacked panels.

```
← All events
┌OCT┐ Laser cutter induction                   ( View page ↗ ) [■ Open check-in ]
│16 │ (Published) Public · Tomorrow, 6:30 PM · 12 / 16 places
Overview  Registrations 14  Check-in  Tickets & invites  Feedback  Team  Settings
```

| Tab | Content (existing components) |
|---|---|
| Overview | Stat cards (Going n/cap with bar · Waitlist · Awaiting approval · Invites sent), "Latest registrations" list (5 rows + "All registrations →"), an "At a glance" card (When, Where, Who can join, Price), and the door-ready CTA card when tomorrow or today and offline check-in is enabled. |
| Registrations | `EventRegistrationRoster` as a P14 table with status pills (Going, Waitlist, Pending) and inline Approve / Decline… for pending; `EventRegisterMember` as "+ Add registration" (outline). |
| Check-in | The Y8 layout: progress stat plus offline callout (`OfflineCheckInOperator`), camera and Start scanning (`EventCheckInScanner`), find a guest, toggles, Recent check-ins with **inline Undo only if the backend supports reversing a check-in** (otherwise omit; do not fake it), and the door-station card (`EventStationSettings`). |
| Tickets & invites | `EventTicketsPanel`, `EventPromosPanel`, `EventInvitesPanel`, each a section; shown only for enabled `ticketing_features`. |
| Feedback | `EventFeedbackPanel` and responses; certificates (`EventCertificateActions`). |
| Team | `EventOrganizers`, `EventCollaborators`. |
| Settings | Image (`ImageUploader`), `EventFields` as settings rows, `EventCategoriesField`, series overrides ("Reset to series value" per field), Discard/Save; lifecycle at the end: Complete (outline) and a danger card "Cancel event… Registrants are notified and registration closes." |

- **Header primary by status:** draft → "Publish…" (confirm, because it notifies the public);
  published → "Open check-in" (hidden on the Check-in tab); completed → "View feedback".
  Cancelled or completed: a read-only banner "This event is completed. It can't be edited."
- **Series** (`EventSeriesDrawer`) gets the same page treatment per Y10: upcoming-date cards,
  details, a "Who can join" chip radio, agenda, and the "Delete series…" danger zone.

### S13. Bookings (`bookings`) ← Y2 + Y7

**Layout:** L3 `ListLayout`. The slots are filled as follows: `stats`; `tabs` = Requests /
Upcoming / Spaces (or Spaces only in the minimum variant); `body` = rows. The space detail is L4
`DetailLayout` (page). "+ New space" is L6.

```
Bookings                                                   ( + New booking ) [■ + New space ]
┌Awaiting approval 1┐┌Today 4┐┌This week 19┐┌Spaces 6┐   ← approval count from dashboard; others only if available
Requests 1 │ Upcoming │ Spaces 6
Spaces tab rows: [tile] Woodshop bench · Workshop · (Staff approval) (Public) (Active) · "3 today" ⋯
```

- Today the page lists spaces only; booking requests live inside each space's `BookingDrawer`.
  **Minimum change:** the spaces list as P6 rows with pills replacing the 5-column table, and the
  "Awaiting approval" stat linking to the first space with pending requests. **Better** (needs a
  cross-space bookings list endpoint, so flag it): the Requests and Upcoming tabs.
- The space detail opens as a page (Y7 pattern) with tabs Calendar, Requests, Settings (the
  `BookableSpaceForm` rows) and Danger (deactivate).
- **Empty:** "No bookable spaces yet. Create one to start taking bookings."

### S14. Reports (`reports`) ← Y6 (form card) + P4

**Layout:** L4 `DetailLayout` (page) with `asideSide="start"`. The slots are filled as follows:
`aside` = the grouped report list; `title` = the selected report; `actions` = Export primary and
Schedule secondary; `main` = filter bar, stats, chart and table. No `back` and no `identity`:
this is the one sanctioned L4 variant without them.

```
Reports                                          ( Schedule… ) [■ Export ▾ ]
Operations reporting for Fab Lab Kochi.
┌ Report list (240) ────────┐  Loan throughput
│ LENDING                   │  [7 days | 30 days | Quarter | Custom ▾]  Grain [Day ▾]  ☐ All makerspaces*
│ ▣ Summary                 │  ┌Products┐┌Active loans┐┌Damaged┐┌Missing┐
│   Taken items  Active…    │  chart (existing hand SVG)
│ INVENTORY …  MACHINES …   │  table (OperationsReportTable)  Saved views ▾  Columns ▾
│ COMMUNITY … MONEY … SYSTEM│
└───────────────────────────┘
```

- Replace the 28-option `<select>` with a grouped left list (eyebrow group labels). Unavailable
  reports show as disabled rows with `unavailable_reason` in a tooltip and a muted "Needs
  Bookings module".
- Date presets as a segmented control plus custom inputs. **Export** is the primary because it is
  the page's output. Schedule (`ReportSchedules`) opens a drawer.
- **Mobile:** the report list becomes a select sheet at the top.
- **Empty data:** "No activity in this period. Try a longer range."

### S15. Audit log (`audit`) ← Y1/Y2 activity rail as a full list + P14

**Layout:** L3 `ListLayout width="wide"`. The slots are filled as follows: `callout` =
verification status (success pill, or a danger panel if broken); `filters` = AuditLogFilters with
chips; `body` = rows (activity items grouped by day); `pagination`.

```
Audit log                                                        ( Export )†
Every state change in this makerspace, append-only.
(✓ Chain verified · checked 2 min ago)  ← AuditVerificationStatus as a status pill/callout (danger callout if broken)
[Actor ▾] [Action ▾] [Target ▾] [Date range]  Sort ▾   (AuditLogFilters as a filter bar; active filters as removable chips)
TODAY
(PO) Priya accepted request #1042 · Meera Nair                  10:57 · request:1042  ▸ details
(DP) Dev uploaded return photo #182 · request #1039             10:47
YESTERDAY …
```
† only if an export endpoint exists; otherwise omit.

- The row is the activity-rail sentence (actor bold, `action_label`, target as a link where a
  console route exists). The raw `action` key and the meta go into a "details" disclosure
  (monospace key–value). Keep "(some details withheld)" when redacted.
- Group by day with sticky day headers. Use keyset-friendly "Load more" or keep the current
  pagination at the bottom ("Page 2 · 1,204 entries").
- **Empty with filters:** "No entries match these filters. Clear filters."
- No Undo or edit affordances anywhere (append-only).

### S16. Member area home and tabs (`/member`, `/member/:tab`) ← Y1 (home), Y26 (card), Y16 (account)

**Layout:** L1 `AppShell variant="member" compactNav="bottom-tabs"`. Home = L2
`DashboardLayout` (`rail` = notices). Loans, Bookings, Events, Payments and Inbox = L3
`ListLayout`. Account = L5 `SettingsLayout`. The signed-out or not-a-member home = L9
`PublicLayout` + `PublicDetailLayout` (the join card as `actionCard`). The member card full view
= L9 `width="narrow"` with the ticket (P27).

```
Desktop: member sidebar (logo, space switcher card = makerspace + membership status, nav: Home · Loans · Bookings · Events · Payments · Inbox · Account, bottom: user chip / Sign out)
Mobile:  top bar + bottom tabs: Home · Loans · Bookings · Events · More (Payments, Inbox, Account)

Hi Meera                                                   [■ Start visit ]*  ← presence, when module on
Fab Lab Kochi · Member since March 2026  (Active)
┌ ! Accept the updated waiver (v3) to keep borrowing.                       Read and accept → ┐
┌On loan 2┐┌Due this week 1┐┌Bookings 1┐┌Payments due ₹500┐
Coming up                                         Notices
┌OCT┐ Return Multimeter          Due Fri (Renew)    • Your request #1042 was accepted
┌OCT┐ Woodshop bench 10:00–12:00 (Confirmed)        • Booking confirmed
Your member card ▸ (ticket card with QR — opens the full card)
```
\* "Start visit" / "End visit" maps to the presence session today ("Start 2-hour presence").

- Navigation is the existing `memberTabs(modules)`. Keep `role=tablist` semantics on the nav, or
  convert to links (PLAN Phase 4 decision). Keep the `#main-content` target.
- **Callout priority:** waiver acceptance needed, then a payment due, then an overdue loan, then
  application status ("Your application is waiting for 2 vouches").
- **Not a member / signed out:** the home becomes the join page. A Y23-style card ("Join Fab Lab
  Kochi": policy summary, `AdmissionJoin` / `JoinMembershipCta` as the primary, "Have an
  account? Sign in") beside a description of what membership gives. `InvitationRequestForm` and
  `MemberClaimRedemption` are secondary links.
- **Loans tab:** "On loan" rows (due chip, item, Renew if allowed) and a "History" section
  (`MemberHistory`). **Payments:** dues stat cards plus `MemberPaymentRows` with an inline "Pay"
  primary pill per row; archived payments as a link row at the bottom. **Inbox:**
  `MemberNotices` and `MemberNotifications`; empty "No notices need your attention." **Account:**
  the Y16 settings rows (profile, two-step sign-in link, `MemberCertifications`, referrals,
  directory listing) and the member card.
- **Member card** (`MemberCardPanel`) = the **Y26 ticket**: a makerspace header band, a name /
  member since / role grid, a perforation, the QR, the caption "Show this at the desk. It only
  holds a private member link." (verify that statement against the card payload before using it),
  and "Add to wallet" / "Save card" where supported. Offline note when cached.
- **Restoring state:** a full-page skeleton of the shell, not "Restoring session…" text.

### S17. Public catalogue (`/m/:slug`) ← Y18 (sticky right card) + P10 chips

**Layout:** L9 `PublicLayout width="wide"`. The slots are filled as follows: `aside` =
`ActionCard` (the request cart: `form` = purpose and contact fields, `primary` = "Send request —
n items", `mobileBar`); `children` = the header block, search, the category chips and the product
grid (an L3-style body without the app shell).

```
[logo] Fab Lab Kochi          Catalogue  Events  Machines  Book a space          ( Sign in )
──────────────────────────────────────────────────────────────────────────────────────────
Borrow tools from Fab Lab Kochi                         ┌ Your request ─────────────────┐ 340w sticky
248 tools and kits · members borrow free                │ 2 items                        │
[ Search tools, machines, kits, materials        ⌕ ]   │ Arduino Uno        − 1 +       │
(All)(Electronics)(Woodwork)(Textiles)(3D printing)…    │ Multimeter         − 1 +       │
Sort: Name ▾                                            │ What's it for?  [            ] │
┌card┐┌card┐┌card┐                                     │ [■ Send request — 2 items ]    │
│img │ │img │ │img │  name, availability pill (word),   │ Staff review every request     │
│    │ │    │ │    │  "Add" stepper                      │ before anything is handed over.│
└────┘ └────┘ └────┘                                    │ ( Borrow | Scan a tool )  seg. │
‹ Prev  Page 2 of 11  Next ›                            └────────────────────────────────┘
footer: [logo] Powered by space works · Privacy · Terms
```

- **Shared `PublicShell`** (PLAN §3.4): a Y18 48 px header with the makerspace brand, then nav
  links (only the modules that are on), then a "Sign in" outline pill.
- The category sidebar becomes a **chip row** (scrollable) at <1280 and stays a left list at
  ≥1280 if there are more than 8 categories.
- **Request panel = the Y18/Y23 sticky card.** Its counts and title change with state: empty
  ("Nothing added yet. Tap Add on any tool."), with items, submitted (a success state in the card:
  "Request sent. We'll email you when it's ready.", plus the public token link). The Borrow/Scan
  switch is a P9 segmented control. Access-policy copy (the three variants in
  `PublicRequestPanel`) stays verbatim in meaning, as the card's helper.
- Disabled requests: the card says "This makerspace shows its inventory but doesn't take requests
  online." with no primary.
- **Mobile:** the card becomes a **sticky bottom bar** ("2 items · Review request") that opens a
  bottom sheet with the same content.
- **Never expose** locations, box IDs, QR, evidence or hidden counts. The availability pill shows
  `exact_count` only when allowed, else the status word.

### S18. Public item detail (`/items/:itemId`) ← Y21 (detail with right rail) + Y18 sticky card

**Layout:** L9 `PublicLayout` + `PublicDetailLayout`. The slots are filled as follows: `cover` =
item image; `chips` = category and kit; `sections` = Description and Borrowing terms;
`actionCard` = availability, "Add to request", "Notify me". Not-found = L8 `CenteredCardLayout`.

```
Fab Lab Kochi / Catalogue / Arduino Uno R3            (breadcrumb)
[ image 16:10, r16 ]                                  ┌ (Available) ────────────────┐
(Electronics)(Kit)                                    │ 3 available  (only if exact)│
Arduino Uno R3   (48 bold)                            │ [■ Add to request ]         │
description…                                          │ ( Notify me when it's back )│ (when unavailable + feature)
Borrowing terms (grey inset box)                      └─────────────────────────────┘
```

- "Add to request" adds to the same cart (shared `useInventoryCart` state) and links back to the
  catalogue with the card open. Today the page says "Request from the catalogue". This is a
  behaviour improvement within the frontend; **flag it** for approval.
- **Not found:** a centred card "This item isn't in the public catalogue." with "Back to the
  catalogue".

### S19. Public event page (`/events/:publicToken`) ← Y18, Y19, Y23, plus Y26 confirmation

**Layout:** L9 `PublicLayout` + `PublicDetailLayout`. The slots are filled as follows: `facts` =
date chip block and venue block; `sections` = About / Schedule / Speakers / Venue / FAQ (only
non-empty ones); `actionCard` = Join card (`form` inline when short), with `state`
open/closed/done; `host`. The events list = L9 + L3-style rows. Feedback, ticket and running
order = L9 `width="narrow"`.

- The layout is exactly P25. Map the existing pieces: image as cover, title, starts_at and
  location in the date and venue blocks, category and tags as meta chips, description, and
  `EventPrice` folded into the CTA label ("Register — ₹200", "Register — it's free",
  "Join waitlist", "Apply").
- **Registration form placement:** inside the sticky card when the form is short (no
  `custom_form` and no ticket choice, the Y23 pattern); otherwise the card CTA opens a modal or
  sheet with `EventRegistrationForm` (tickets, promo, custom fields).
- "Add to calendar" and "Share" are the two outline half-buttons in the card. The share error
  becomes a toast ("Couldn't share. Link copied instead." when the clipboard fallback succeeds).
- **Closed:** the card shows "Registration is closed" plus the cutoff time, with no primary.
  **Not found:** a centred card.
- **After registering:** a confirmation state in the card, then a link to the **ticket page**
  (Y26) if tickets or check-in exist.
- **Events list** (`/events`): P6 date-chip rows grouped by series (series eyebrow), with search
  and filters (Free, Registration open) as chips and the calendar view as a segmented toggle
  (List | Calendar). The inline "Register" expand-in-place becomes a link to the event page (one
  primary per page; forms live on the event page).
- **Feedback page** (`/events/:token/feedback`) = Y25 exactly.

### S20. Staff sign-in (`LoginPanel`) ← Y11

**Layout:** L8 `AuthLayout`. The slots are filled as follows: `brand.headline` = the accent
phrase; `brand.showcase` = floating SpaceWorks object cards; `eyebrow` = Staff console or Front
desk; `title` = "Welcome back."; `social`; `form` = Username and Password; no `modeSwitch`.

- Split screen. **Left:** the space works horizontal logo; the headline **"Welcome back."**; an
  eyebrow above it, "Staff console" or "Front desk" (for `guestOnly`); social buttons first when
  configured, then the divider "or with your username"; the **labels "Username" and "Password"**
  (test pins); "Forgot?" on the password label row (only when `emailEnabled`); a show-password
  toggle; the full-width primary "Sign in" with a spinner and "Signing in…". The error appears
  as an inline danger text under the fields with `role=alert`. If password sign-in is off:
  "This deployment signs staff in through an identity provider." with the IdP buttons only.
- **Right brand panel:** a tinted panel with the one Unbounded accent phrase ("Less searching.
  More making."). Three floating product cards drawn from real SpaceWorks objects (a due-date
  chip card "Multimeter · due back Fri", "Request #1042 · Ready for handover", and a chip
  "✓ Return photo attached"). Decorative only, so `aria-hidden`.
- **No segmented Sign in / Create account** (staff accounts are invited).
- **Mobile:** the brand panel collapses to a 120 px band above the form or is hidden.

### S21. Member sign-in / sign-up (`MemberAuthPanel`) ← Y11, Y12, Y13

**Layout:** L8 `AuthLayout` with `brand.tenant`. The slots are filled as follows: `modeSwitch`
when self-serve. Verify, MFA and reset = L8 `CenteredCardLayout` (`media.icon`, `content` = code
boxes or the strength meter).

- Split screen as in S20, but the makerspace's branding takes the right panel (tenant colour,
  logo, the welcome line from branding). The segmented control **Sign in | Create account**
  appears only when `selfServeAccounts`; otherwise the muted line "This space doesn't run self
  sign-up. Ask a staff member to add you."
- Sign-up fields: Name, Email, Password (with the Y12 strength meter and rule list), Phone ·
  Optional. Helper under Create account: "One account works at every makerspace you join."
- **Verify email** = a Y13 centred card (envelope tile): "Check your email", "We sent a code to
  **meera@…**", a 6-box code input (the P28 digit boxes at 46×56 with `autocomplete=one-time-code`
  on a single hidden input for paste), primary "Verify email", link "Resend code" (with a
  countdown).
- **MFA** (`MfaFlow`) uses the same centred card with code boxes and "Use a recovery code
  instead". **Reset password** (`PasswordRecoveryFlow`, `ResetPasswordPage`) = Y12 exactly.

### S22. Invitation accept (`StaffInvitationAcceptPage`, `OrganizationInvitationRedeemPage`) ← Y14, Y15

**Layout:** L8 `CenteredCardLayout width=480`. The slots are filled as follows: `media.avatars`
for a staff invite or `media.banner` for an organization invite; `content` = the password field
plus the MFA disclosure; `primary` = "Accept invitation"; `footer` = account hint.

```
              ┌──────────────────────────────────────┐
              │        [FK][PO]  (tile + avatar)      │
              │   You've been invited to join          │
              │        Fab Lab Kochi                    │
              │        (as Inventory Manager)           │
              │ You'll manage this space's inventory.   │
              │ Password                                │
              │ [                                   👁] │
              │ ▸ My account uses two-step sign-in      │ (reveals code field)
              │ [■■■■■■■ Accept invitation ■■■■■■■■]   │
              │ Already have an account? Use its        │
              │ current password.                       │
              └──────────────────────────────────────┘
```

- The makerspace name and role need invite-preview data. The token is in the URL hash and the
  page fetches nothing today. **Flag:** without a preview endpoint, show "You've been invited to
  join a makerspace on space works" and drop the role pill. Do not guess.
- The MFA code field moves behind a disclosure (progressive), with the current label preserved
  inside.
- **Success:** a centred success card "You're in." plus a "Sign in" primary (today a link).
- **Invalid or used token:** "This invite link has already been used or has expired. Ask the
  person who invited you for a new one."
- An organization invite uses the Y15 banner variant (organization colour band) with the scope
  sentence.

### S23. Kiosk station (`/kiosk/:stationToken`, `KioskStationPage`) ← Y27, Y28

**Layout:** L10 `KioskLayout`. The slots are filled as follows: `mode` lock → ready → work;
`lock.pinLength=8`; `work.capture` = `KioskOnlineScanner`; `work.panel` = L7 `FlowLayout
presentation="kiosk"` (the handover) or the result card; `confirmLock` = the pending-work discard
dialog; `idleCountdown`. The offline queue renders in `work.panel` as a table plus a panel
callout.

- **Locked:** the Y27 layout. Makerspace tile, the context line "Fab Lab Kochi · Handover
  station", the title "Enter the station PIN", the helper "Ask a manager for the 8-digit PIN. It
  unlocks this device only.", **8 digit boxes** (the current PIN is exactly 8 digits) plus the
  keypad, and "Unlock station" disabled until 8. The keypad must not break hardware-keyboard entry
  (one hidden numeric input drives the boxes). Offline-locked: the same screen with the CTA
  replaced by "Reconnect to unlock this station" and an "Offline" pill.
- **Unlocked, no operator:** a centred card "Station ready", the station name and kind, and the
  primary "Start operator shift" (disabled offline, with the reason).
- **Working:** the Y28 layout. Header: station name, "Fab Lab Kochi · Handover station",
  right side shows the **queue count** ("2 waiting"), an "● Online" / "● Offline · 3 queued"
  pill, "Full screen" (icon button) and "Lock station" (outline). Body: camera left
  (`KioskOnlineScanner`), right = the current handover (`KioskOnlineHandover`) as the S3 steps in
  large-touch mode, or the **result card** after each scan (green success, red "Not this
  station's item" error, yellow "Queued offline · will sync"). Recent list under the result.
- **Offline queue mode** (`KioskOfflineHandover`): a P5 panel callout "Offline. Handovers are
  encrypted on this device and sync when you reconnect." with a "Retry now" button. The queue is
  a P14 table (status pill per command: Queued, Syncing, Failed and needs review).
- **Lock with pending work** = a danger dialog, not inline text: "Discard local work and lock?
  This clears 3 encrypted handovers and their photos from this device. This can't be undone."
  Buttons "Keep working" (primary) and "Discard and lock" (red outline). The safe option is the
  primary.
- **Idle reset** shows a 10 s countdown overlay ("Locking for privacy in 10… Tap to keep
  working") before locking when no work is pending.
- **Event door station** (`/event-check-in/:stationToken`) = Y27 then Y28 one-to-one.

### S24. Remaining staff tabs (Phase 6 sweep), pattern assignment

Pointer only. The long tail is specified in depth in `research/ux-screens-longtail.md`, which
must use the layout names from §1A.11. The assignments below are the default layout per tab.

| Tab | Layout · pattern |
|---|---|
| notifications (Inbox) | L3 · P12 rows grouped by day, unread dot, "Mark all read" outline, filter tabs All / Unread; empty "You're all caught up." |
| handover (Job pickups) | L3 + L7 · S2 row pattern: tabs Ready / Collected; inline "Hand over" opens `HandoverConsole` in S3 task mode (photo rules as today). |
| payments | L3 · Stat cards (Outstanding, Collected this month, Awaiting settlement), tabs Outstanding / Settled / Refunds, P14 table with inline "Record payment…" (`SettlementDialog`); never Undo (append-only receipts; corrections are `amends`). |
| ledger, transfers, stocktake, needsfix, tobuy, containers, categories | L3 (stocktake session = L7) · Dense-table adaptation (§5.1) with PageHeader plus one primary each: "+ New transfer", "Start stocktake", "+ Add to list", "+ New container", "+ New category"; needsfix rows get inline "Back in stock" / "Write off…". |
| qr, scanner, bulk | L6 `width="narrow"` · Tool pages: centred 720 column, P21 camera block for the scanner, P18 dropzone for bulk import with a validation preview table. |
| warranty, devices | L3 + L4 drawer · Table plus drawer detail with P15 rows. |
| cards (Member cards) | L3 · Camera scan block plus the card list; the scan result as a P29 result card. |
| accountability | L3 · Table of borrowers with restriction status pills; row menu Restrict… / Restore. |
| organized, organization-analytics, organizations | L2 / L3 / L4-report · Y1 org cards for organizations; organized events reuse S11 rows; analytics reuses S14. |
| emailtemplates, email-logs, api | L6 / L3 / L5 · Y6 patterns (form card, empty state, code/accordion) for api; logs as a P14 table with status pills; templates as a list plus an editor page with a live preview (P18). |
| exports, backups, migration, usage, modules, platform* | L5 (restore/migration runs = L7) · P15 settings rows plus P16 danger cards for restore/purge; jobs show progress rows (JobTray). |

---

## 4. UX quality bar (every screen, app-wide; implementation must pass every applicable item)

This applies to every routed screen, whether it is specified here or in `ux-screens-longtail.md`,
across staff, member, public, auth and kiosk. Run it per screen at review time.

**Composition**
- [ ] The screen is exactly one shell plus one layout from §1A (L1–L10), with slots filled. There
      is no bespoke page-level grid, header or empty/error handling outside the layout. Any
      deviation is listed in the PR with a reason.
- [ ] The layout receives already-gated tabs, nav and actions. The screen adds no gating
      branches to the layout.

**Structure**
- [ ] Exactly **one** filled primary per view region (page header, drawer footer, sticky card,
      callout). It never targets the current screen.
- [ ] A title plus either a greeting/date eyebrow (landing pages) or a one-sentence scope subtitle
      (inner pages). Detail pages: back link, identity tile, title, status pill, meta line.
- [ ] Detail views use underline tabs that are URL-addressable. Tabs whose content is gated are
      absent, not disabled.
- [ ] Counts live in stat cards, tab labels, row right slots or header meta. The sidebar carries
      only Inbox unread and the Requests needs-action count.
- [ ] A callout appears only when actionable now. At most one per screen. It has a bold lead
      clause, a consequence and an action.
- [ ] Destructive-irreversible actions sit in a danger card at the end, with a "…" button that
      opens a confirmation naming the object and the consequence.

**Lists**
- [ ] Every list has an empty state that names the situation **and** the next step, pointing at a
      visible control. Filtered-empty differs from truly-empty and offers "Clear filters".
- [ ] Rows have one inline next-step action; everything else is in the row menu.
- [ ] Loading = skeletons in final geometry; error = inline block plus Retry; pagination states
      "1–24 of 248".
- [ ] Status is never colour-only: every pill has a word, and overdue chips carry "Overdue n days".

**Feedback and safety**
- [ ] Reversible actions run immediately with **Undo** (inline where the row stays, toast where it
      leaves the view), using the existing `toastStore` awaited compensation. Undo is never
      offered for evidence, handovers, audit, payments or settlements.
- [ ] Hard-rule steps show **why** the primary is disabled ("Add the return photo and a remark to
      continue.").
- [ ] Saves: an explicit Discard/Save that appears when dirty for field groups; instant toggles
      confirm with a toast. Never two save models in one section.
- [ ] Every mutation has a pending label ("Saving…") and disables only its own control.

**Copy**
- [ ] Sentence case; consequence-first helpers; numbers in context ("12 / 16 going", "Due Fri");
      relative times with the absolute time in `title`/tooltip; "…" on buttons that confirm; "↗"
      on external links.
- [ ] Error copy says what failed and what to do ("Couldn't save. Try again."), never raw codes.

**Access and devices**
- [ ] Keyboard: the full flow is reachable by Tab; tabs use roving focus with arrows and
      Home/End; Esc closes drawers and modals and returns focus to the opener; Ctrl/⌘K opens the
      palette from anywhere.
- [ ] Focus ring ≥3:1; 44 px minimum targets; one `h1`; the skip link targets `#main-content`
      (`tabIndex=-1`); collapsed content unmounted; reduced motion respected (no auto-advance
      animation, a quick fade only).
- [ ] Mobile (375): no horizontal page scroll; header collapses to primary plus ⋯; tables become
      stacked cards; sticky primary at the bottom where the task is the page (handover, request
      cart, register); drawers go full screen.
- [ ] Camera views start only on explicit intent, except task-mode scan steps where scanning *is*
      the step. There is always a manual-entry fallback under the camera.
- [ ] Test pins (PLAN §2) are preserved or deliberately updated in the same commit.

---

## 5. Where Yuyu doesn't fit, and the adaptation

### 5.1 Dense operational tables (Inventory, Ledger, Stocktake, Transfers, Audit, Reports, Payments)

Yuyu's biggest list has 4 rows and 3 columns. SpaceWorks lists run to hundreds of rows and 8+
numeric columns, sorted, selected in bulk and exported. **Card rows (82 px) would cut density by
about 60%.**
- **Adaptation:** keep `DataTable`, but inside the Y4 card chrome (bordered, radius 12; header row
  40 tall with 13 muted sentence-case labels; body rows **52–56** tall; hairlines; tabular
  numerals right-aligned). Sticky header. A column picker. A selection checkbox column, and the
  bulk bar (sticky) instead of toolbar buttons. Row click opens the detail; the row menu holds
  the rest.
- Filters as tabs (P8) for the 3–5 most common states. Everything else goes in a "Filters"
  popover with removable chips.
- Under `md`, rows become stacked cards (PLAN §3.5 `DataTable` addition).
- Stat cards above a table only when they are **also filters** (clicking "Low stock 12" applies
  the tab).

### 5.2 Evidence capture (issue/return photo, remark, box and asset QR)

Yuyu captures nothing heavier than a QR scan. SpaceWorks evidence is mandatory, immutable,
uploaded through a presign to staging, and auditable.
- **Evidence tile** (new primitive): a 16:9 dashed placeholder labelled "Issue photo · Required"
  with "Take photo" (primary, uses the existing `CameraCapture`) and "Upload from device" (link).
  The states are uploading (progress bar plus cancel), attached (thumbnail, "Photo #182 ·
  attached 10:42", "Retake"), and error ("Upload failed. Your photo is still on this device. Try
  again.").
- It is **never** displayed via a public URL. Previews use the signed-URL fetch already in
  `QueuesList`.
- **No Undo after confirm:** the summary before confirming replaces it (S3 step 4). Copy must not
  promise deletion of an uploaded photo unless the deployment's abandoned-upload cleanup is on.
- **Required-ness is visible before the user reaches the button:** a "Required" chip on the
  step, and a step rail showing a red dot for missing required evidence.

### 5.3 Multi-step guided flows

Yuyu has none (its forms are single page). SpaceWorks has 5-step handovers in modals.
**Adaptation:** a task-mode shell (sidebar hidden, step rail plus a camera/work panel, the same
on kiosk), visually derived from Y28. A "Compact view" for experts. Each completed step echoes
its captured value in the rail.

### 5.4 Permission and module density

Yuyu has 4 nav items and owner/admin roles. SpaceWorks has 42 gated tabs, custom roles with
dozens of actions, and module switches. **Adaptation:** §2 sections with "More" disclosure and
flattening rules. The role editor uses Y6 checkbox cards grouped by area rather than a flat
checkbox list. Gated items are **absent, never disabled**, except reports, where an unavailable
report explains which module enables it.

### 5.5 Settings scale

Yuyu settings is 3 rows. SpaceWorks has about 30 sections. **Adaptation:** an in-page sub-nav
with scroll-spy (S9), a per-section dirty-state Save, and one danger zone at the very end.

### 5.6 Dashboard breadth

Yuyu shows 4 stats. SpaceWorks has 17 possible tiles. **Adaptation:** priority-ranked top 4 plus
an "Everything else" disclosure. Tone on the number, not the fill.

### 5.7 Multi-tenant switching

Yuyu shows one org in the switcher. Superadmins may see dozens of makerspaces. **Adaptation:** the
switcher menu has search, recents first, and a "Switch makerspace" full list for superadmin.
Single-tenant lock hides the chevron (the card is static).

### 5.8 Offline and kiosk integrity

Yuyu's offline story is a callout with "Download guest list". SpaceWorks kiosks keep an encrypted
command queue with replay recovery. **Adaptation:** a persistent connection pill in the station
header, P5 panel callouts for offline state, a queue table with per-command status, and a
destructive-confirm dialog for "lock with pending work" (safe action as primary).

### 5.9 Money

Yuyu has free events only. Payments need receipts and append-only corrections. **Adaptation:** no
Undo and no inline edit. "Record payment…" opens `SettlementDialog` (method, reference, date).
Corrections appear as "Amended" rows linked to the original. Amounts are always shown with
currency, right-aligned with tabular numerals.

### 5.10 Activity rail data

Yuyu's rail is free. SpaceWorks audit is permission-gated and can be large. **Adaptation:** the
rail renders only when `canViewAudit` (or uses the actor's own notifications), is capped at 6
items, and links to S15 with filters. It is hidden on narrow screens and for scoped roles whose
audit would be empty.

---

## 6. Items that need a decision or data before implementation

1. **Request tab counts and the sidebar Requests badge.** Use per-query `count` (free in the
   default view) and the cached dashboard query for the sidebar. Confirm the dashboard endpoint
   is readable by every actor who sees Requests; otherwise show no badge for them.
2. **Event check-in Undo** only if a reversal endpoint exists. Do not render Undo otherwise.
3. **Invite preview** (makerspace name and role on S22) needs a token-preview endpoint; fall
   back to generic copy.
4. **Cross-space bookings list** for the S13 Requests and Upcoming tabs. Without it, use the
   minimum variant.
5. **Event aggregate stats** (Going, Awaiting approval) need server counts; never sum a page.
6. **Public item "Add to request"** (S18) is a small behaviour change (shared cart across
   routes). It needs owner approval.
7. **Settings deep links:** in-page anchors (no routing change, recommended) vs
   `settings/<section>` subpaths.
8. **Test pins** that change: Dashboard `h1` (keep), the "Inventory" nav label becoming "Items"
   (the panel heading pin is kept), member `role=tab` (PLAN Phase 4), and the dock test moving to
   the sidebar test.
9. **Primary colour** (PLAN open question 3) affects only fills. Every pattern above is
   colour-agnostic.
