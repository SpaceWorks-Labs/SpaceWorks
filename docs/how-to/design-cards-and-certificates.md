---
title: Design cards and certificates
group: How-to guides
order: 132
summary: Use the Card Studio to design member cards, badges, tickets and event certificates, start from a template, print with bleed and crop marks, and print cards from a CSV.
---

# Design cards and certificates

Member cards, staff cards, event badges, tickets and event certificates are all designed in the **Card Studio** and
printed by the same engine, so what you see in the designer is what prints. This guide covers the parts you use every
day. For the rules behind them see [Memberships](../modules/memberships.md) and
[Events](../modules/events.md#certificates-on-card-studio).

## What you need first

- Card management in the space (member cards, ID programmes, staff cards or events), or *edit details* on the event
  for a certificate.
- For certificates: the event's **Certificate designer** switch (`events.certificate_designer`) on, and, if you want a
  signature, at least one signatory added under the event's certificate signatories.

## Quick mode or Advanced mode

Every design opens in **Quick** mode the first time: pick a **Style** (a template), set the background, text and accent
colours from the brand palette or any custom colour, choose the paper and turn it sideways, switch items on and off, add
a data field, and add a logo or background picture. **Advanced** gives you the whole canvas. The choice is remembered in
your browser, and both modes edit the same design.

On a **phone** the studio shows the card as a preview with Quick edits only (colours, text, paper); layers can't be
dragged on a small touch screen. Open it on a tablet or computer for Advanced mode.

In Advanced mode the card sits in the middle, the tool rail and its panel on the left (**Add**, **Layers**,
**Background**, **Library**, **Templates**, **Page**, **Checks**, **History**) and the selected layer's settings on the
right.

- **Select**: click, Shift-click to add, or drag a box on the card to select everything it touches. **Tab** moves through
  the layers; the **Layers** tab is the keyboard alternative to dragging: reorder with the arrows or Alt + Up/Down, rename,
  lock, hide, group and delete.
- **Arrange**: the bar above the card aligns (to the card, to the selection or to the safe area) and spaces evenly,
  brings forward or to the front, sends backward or to the back, groups, locks and hides. Dragging snaps to the card
  edges and centre, other layers, equal gaps, the safe zone, the printer margin and your guide lines; hold Alt to move
  freely. Shift keeps proportions when resizing and turns in 15 degree steps.
- **Rulers and guides**: millimetre rulers run along the top and left of the card; click a ruler to drop a guide line
  there (up to 20; edit or remove them in **Page**). The red band outside the card is the bleed (see below).
- **Zoom**: the zoom buttons, Ctrl or Cmd + plus, minus or 0 (fit), Ctrl + wheel or a two-finger pinch.
- **Shapes, lines and icons**: rectangles, rounded rectangles, circles, ellipses, arches, lines, triangles, diamonds,
  hexagons and stars, each with a fill or gradient, an outline, corner radius, opacity and a shadow. **Icons** come from
  a built-in library of 30 (location pin, phone, envelope, calendar, ID card, award, gear and more) in any colour.
- **Rich text**: type the text, select some words, then make just those words bold, a different colour, size or font.
  Add letter spacing, line height, an outline, a highlight bar, an underline bar and a shadow. Fonts are limited to the
  Card Studio list so every device and the printer agree.
- **Backgrounds**: colour, gradient (up to 6 stops, linear or radial) or a picture with fit, zoom, focal point, blur and
  darken, plus an **overlay** fade for legibility.
- **Guides** tab: bleed, safe zone, printer margin, a lanyard punch slot and ruler lines, shown only while you design.
- **Preview as**: the owner sample (Shaan Shoukath), two neutral names, the long forms of each, or a real card holder.
- **Undo and history**: every change is one undo step (Ctrl or Cmd + Z, Shift to redo). **History** lists saved versions
  of the design; restore any of them as a new draft, or **Compare with the current version**: the two versions side by
  side (front or back) with what changed outlined (green added, red dashed removed, orange changed) and a list of the
  changed layers in words. Publishing (or approval, when the space requires it) decides what prints.

### Keyboard shortcuts

Press **?** in the studio for this list. Shortcuts never fire while you type in a field.

| Keys | Action |
|---|---|
| Ctrl/Cmd + A, Esc | Select every layer on this side; clear the selection |
| Arrows (Shift: 5 mm) | Move 1 mm |
| Alt + arrows (Shift: 5 mm) | Resize 1 mm |
| Ctrl/Cmd + C, V, D | Copy, paste (also onto the other side), duplicate |
| Delete | Delete the selection (locked layers stay) |
| Ctrl/Cmd + G; Shift + Ctrl/Cmd + G | Group; ungroup |
| Ctrl/Cmd + ] or [ | Bring forward; send backward |
| Shift + Ctrl/Cmd + ] or [ | Bring to front; send to back |
| Shift + Ctrl/Cmd + L | Lock or unlock the selection |
| Shift + Ctrl/Cmd + H | Hide or show the selection |
| Ctrl/Cmd + plus, minus, 0 | Zoom in, zoom out, fit the card |
| Ctrl/Cmd + Z; Shift + Ctrl/Cmd + Z (or Ctrl + Y) | Undo; redo |
| Alt + drag; Alt + click | Move without snapping; pick one layer inside a group |

The certificate designer uses the same shortcuts.

## Start from a template

1. Open the design and choose **Templates**. Built-in looks come in a light and a dark theme: cards (Studio lanyard,
   spotlight, arch and the classic looks) and certificates (**Laurel**, **Ribbon**, **Spotlight**).
2. Pick one and apply it. **Keep my data fields** (on by default) adds any field your old design used that the template
   does not place, as a small line in the bottom-left corner, and tells you which ones; move them where you like.
3. To keep your own look, choose **Save as template** on a finished design. Saved templates are private to the space and
   count toward its `card_templates` limit (a platform operator can set one; the default is none). You can rename,
   duplicate, export (a JSON file) and import them, including on another space.

## Design a card

- **Background**: a colour, a gradient or an uploaded image (fit, zoom, focal point, blur and darken). In print-ready
  exports the background runs on into the bleed (see *Print and export*).
- **Brand kit**: every colour field shows your space's own colours (from its theme) and the Space Works palette as
  one-click swatches. Logos are slots (the space's, the organisation's, the event's or the Space Works symbol), and
  fonts come from the studio's allow-list, so every card prints what the designer shows.
- **Library**: every picture the space uploaded, in any design, is in the **Library** tab: use one as the background or
  add it as an image layer. **Delete** removes a picture nothing uses any more and gives its storage back; a picture
  still used by a design, a saved version or a template is kept.
- **Text**: one layer can mix weights, colours and fonts. Fonts come from an allow-list of open faces; a font that is not
  ready falls back to a safe face. Text must keep 4.5:1 contrast against what is under it, except lettering you mark as
  decorative.
- **Barcodes**: Code 128 (the default), Code 39, EAN-13, UPC-A, PDF417, Data Matrix and Aztec, carrying the card number
  (or, for Code 128, PDF417, Data Matrix and Aztec, the private desk code). EAN-13 and UPC-A carry digits only: a card
  number with letters prints nothing in those types, so pick them only for numeric numbering. Each type has a minimum
  printed size (Code 128: 30 x 6 mm, Code 39: 40 x 8 mm, EAN-13 and UPC-A: 30 x 10 mm, PDF417: 30 x 8 mm, Data Matrix and
  Aztec: 10 x 10 mm; the desk code needs more). The designer draws the server's own encoding, so the preview carries
  exactly the modules that print.
- **Photo**: circle, rounded, square or arch, zoom and focal point (the crop), a sticker outline and a drop shadow, and
  the **cut-out** or **each holder's choice** versions when the background eraser is set up
  ([Remove card photo backgrounds](background-eraser.md)); without a cut-out the original photo is used.
- **Guides**: safe zone, margin, ruler lines and a punch slot show in the designer and never print.
- **Check it**: use the sample people (short and long names) and print a test sheet before a bulk run.

## Print and export

Under **File**:

- **Test print**: a PDF at the card's exact size. Print it at 100 % and hold it against a real card.
- **Print-ready PDF (bleed and crop marks)**: the card with the bleed set in **Page** (3 mm when none is set) and crop
  marks in a 7 mm margin, with the PDF trim and bleed boxes a print shop's software reads. The bleed repeats the card's
  outer edge mirrored, so backgrounds and edge-to-edge bands run past the cut with nothing to move. Keep text inside the
  safe zone (dashed line) so the mirror never repeats it.
- **Print-ready PNG (300 dpi, bleed)**: the same card with its bleed, no marks, for online print services.
- **Calibration sheet**: rulers and colour patches to check your printer's scaling.

Proofs from the designer carry the PREVIEW mark. Real cards come from each card's **Download**, which takes the same
print-ready options (`bleed_mm`, `crop_marks`), and from bulk sheets (with crop marks).

### Cards from a CSV file

**File › Cards from a CSV file…** prints one card per row for people who hold no card in Space Works (visitors, one-day
volunteers). The first row names data fields (`name`, `first_name`, `last_name`, `role`, `number`, `valid_until`,
`team`, `field:<key>` and the others in the data-field list); other columns are listed as ignored, and sensitive fields
(blood group, emergency contact) are never filled from a file. Up to 200 rows and 256 KB. The check shows the first three
cards drawn by the server from the **published** version, exactly as the PDF prints them; **Print** makes A4 or Letter
sheets (with crop marks) or one card per page from that same published version. Such cards have no record: their check, desk and check-in QR codes stay empty and photos print
initials. Every run is in the audit log with its row count.

### Print conventions we follow

| Convention | Value in Space Works | Why |
|---|---|---|
| Card size | CR80, 85.6 x 53.98 mm, portrait or landscape (also CR79, CR100, A6, badge and certificate sizes) | ISO/IEC 7810 ID-1, what PVC card printers take |
| Bleed | 0 to 5 mm; 3 mm by default on export (close to the 0.125 in many printers ask for) | The cut can drift; art must run past it |
| Safe zone | 3 mm on cards, 10 mm on certificates | Text and QR codes stay clear of the cut |
| Resolution | 300 dpi rasters (PNG, effects, photo cut-outs) | The native resolution of dye-sublimation card printers |
| Colour | sRGB throughout; no CMYK conversion | Card printers take RGB through their own colour profile; ask a print shop before converting |
| Crop marks | 0.25 pt, starting 1 mm outside the bleed, 5 mm long | Out of the art, inside the page |
| Photo | Head and shoulders, the head filling most of the frame's height (ID photo guidance is 70 to 80 %) | Faces stay recognisable at 25 mm |

Many direct-to-card (dye-sublimation) printers leave a hairline unprinted border; retransfer printers print truly
edge to edge. Either way, the trim the studio shows is the card's edge. Sources: card printer vendors and print
services ([Evolis](https://in.evolis.com/wp-content/uploads/2023/03/brochure-asmi-eng.pdf),
[Entrust card design guide](https://www.entrust.com/sites/default/files/documentation/buyersguide/card-design-guide-artista-cr805-bg.pdf),
[4over4 bleed and crop marks](https://v2.4over4.com/guide/crop-marks-and-bleed-explained-for-print-ready-files),
[Affinity bleed](https://affinity.help/publisher/en-US.lproj/pages/Publishing/bleed.html)) and ICAO-style photo guidance.

## Design an event certificate

1. Under the event's certificate designer, choose a paper size (A4, Letter or A5, landscape or portrait, or a custom size
   up to 420 mm) and a template, or start blank. The 10 mm margin guide shows the safe print area.
2. Place text with the certificate tags: `{{recipient}}`, `{{event}}`, `{{event_date}}`, `{{role}}`, `{{kind}}`,
   `{{award}}`, `{{place}}`, `{{hours}}`, `{{achievement}}` and others (see [Events](../modules/events.md#certificates-on-card-studio)).
3. Add **signature** layers (one per signatory slot) or a **signature row** that spaces several signatories evenly.
   If your space requires signatory approval, a signature prints its image and name only after that person approves the
   design; until then you will see a placeholder line.
4. Add a **seal** (ring, rosette or star, with ring text and a label), the **certificate number** and the **verification
   QR**. The QR and the number are added for you if you forget them and can never be hidden.
5. Optional switch for operators: `CERTIFICATE_SHARED_RENDERER` (default off). When on, a certificate issued from a
   version 2 design is drawn by the shared engine, and that choice is saved inside the certificate so a retry of an older
   one never changes. Studio (version 3) designs always use the shared engine.
6. Save. The new design is used for certificates issued from then on; certificates already issued keep the design they
   were issued with, byte for byte.

## Check it worked

- The designer preview and the preview PDF look the same; the preview QR is a dummy pattern and the serial reads
  `PREVIEW`.
- A test certificate issued to yourself renders with the real serial, a working QR that opens the verification page, and
  the signatories you expect.
- A design that saved before this release still prints as before; nothing needs converting. Icons and the new shapes
  are new optional layer values, so older designs never contain them.

## If something looks wrong

- *"Text is hard to read"* on save: pick a colour with at least 4.5:1 contrast against what lies under the text.
- *"Add signatory N before placing their signature"*: add that signatory first.
- A signature shows only a line: the signatory has not approved the current design, or has not been added.
- A certificate text box overflowing: version 2 designs refuse to print clipped text; enlarge the box or shorten the text.
