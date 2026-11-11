---
title: Design event badges
summary: Design the badge every check-in desk prints, give crew and speakers their own badge, and move designs between events.
order: 62
keywords: badge, badge designer, name badge, lanyard, A6, CR80, role badge, crew badge, speaker badge, watermark, import design, export design, free canvas
modules: events
features: events.badge_designer, events.role_badges
---
The badge designer sets what every check-in desk prints for this event. It saves as you go.

## Design the badge

1. Open the event, then **Cards and tickets**, then **Card design**.
2. The first time, press **Start the badge design**.
3. Choose a **Style** (Classic, Bold or Minimal), the **Colour**, and the **Paper**. Press **Turn to landscape** (or portrait) to turn the stock; pick **Custom** for any size from 40 to 300 mm.
4. Set the **Heading**, **Badge label** and **Footer**. Type `{{team}}` in any of them to print the attendee's team.
5. Under **Logos** and **Show on the badge**, turn items on or off. Under **Registration answers**, add up to 8 answers, then reorder or relabel them.
6. Click an item on the badge to select it. Drag it, or use the arrow keys (Shift moves five grid steps). Set its size, bold and position on the right; **Reset this item** puts it back.
7. Optionally add a text **Watermark** (strength, colour and angle). Image watermarks aren't available on badges.
8. Press **Print test card** to check a sample at actual size, then **Publish badge**. Desks print the published version.

![Screenshot: the badge designer with the settings, the badge and the selected item](screenshot:em-badge-designer)

## Saving and working offline

Changes save a moment after you make them. The status next to the title reads **Saved**, **Unsaved changes**, **Saving…**, **Saved on this device only** or **Not saved**. With no connection, the design is kept on this device and saved when you are back online. If you reopen the designer and the device kept unsaved changes, press **Restore them** or **Discard**. If someone else saved first, choose **Load their version** or **Keep mine**.

## Badges for each role

Where role badges are on, tabs show **Attendee**, **Crew**, **Volunteer**, **Speaker**, **Mentor**, **Judge** and **Organiser**. A role uses the attendee badge until you press **Give … badges their own design**. That makes a copy of the attendee badge with the role's label.

## Move a design between events

Press **Export design** to save the design as a file, then **Import design** in another event. Files from SpaceWorks-Events open too. Answers the new event's form doesn't have are listed, with a button to remove them.

## Convert to a free canvas

**Convert to free canvas…** turns the badge into an ordinary card design you edit layer by layer. This can't be undone; to come back, start a new badge design.

**Who can do this:** anyone who can edit the event. The space turns the designer on or off with `events.badge_designer`, and role badges with `events.role_badges` (both on by default, and both need Event ID cards).
