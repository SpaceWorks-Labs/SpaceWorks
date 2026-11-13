---
title: Use a shelf pointer
group: How-to guides
order: 257
summary: Calibrate a laser or LED shelf pointer, show items on the shelf, guide a stocktake with it, walk the shelves and read past shelf checks.
---

# Use a shelf pointer

A **shelf pointer** is a small laser or LED light, run by a device adapter, that shows where something lives. It is for
staff only: the positions it uses are never shown to the public, never exported and never sent to a browser. SpaceWorks
does not ship the pointer hardware; a Raspberry Pi or ESP32 adapter speaks the [adapter API](../device-adapters/hardware/shelf-pointer.md).

## Before you start

- **Machines integrations** is on for the space (Machines, then the Integrations area; see [manage device adapters](adapter-console.md)).
- A shelf-pointer adapter is enrolled and bound, and you can manage devices.
- Items have a **storage location** (for example `Shelf B3`).

## 1. Calibrate and set the laser limits

1. Open the adapter, then **Shelf pointer**, then **Calibrate**. Pick a storage location, item or box, aim the pointer
   with the jog buttons until it lands on the shelf, and save.
2. Open **Laser limits** on the same screen. Set the **strongest power** (percent) and the **longest time it may stay on**
   (seconds). The server applies both to everything it sends the pointer. With no time limit a laser still stops after
   60 seconds. **Clear** is never limited.

## 2. Show on shelf

Where a calibrated pointer covers the thing you are looking at, **Show on shelf** and **Clear** appear:

- on an **item**, on a **box**, and on each **line** of the issue screen for an accepted request;
- an item with no position of its own uses its storage location's position.

If nothing is shown, no pointer covers it (or Machines integrations is off). Press **Clear** to switch the pointer off.
Each press is recorded in the audit log with your name; the position is never in the record.

## 3. Guide a stocktake with the pointer

In **Stocktake**, open a count and press **Guide with the pointer**. It points at the first shelf with something still
uncounted, and moves to the next shelf as you save counts. A shelf with no saved position is flagged so you can find it by
eye. **Skip this shelf** moves on; **Stop guiding** switches the pointer off.

## 4. Check shelves

In **Stocktake**, open the menu and choose **Check shelves**. Filter to one shelf prefix if you like, then mark each
location **OK** or **Needs attention** (add a note) and press **Save shelf check**. The walk is saved with your name and the
time. **Past shelf checks** lists the earlier ones. The Inventory control report has one row counting the walks, the
locations needing attention and the share that were fine.

Shelf checks are your space's own records: they move with the space when it is moved to another deployment, and they are
not part of any member's personal data export. A hosted space can have a monthly limit on how many checks it saves
("Shelf checks this month"); at the limit a new check is refused until next month, and past checks stay readable.

## Check it worked

- **Show on shelf** appears on a covered item and the pointer moves; the audit log shows "Shelf pointer shown".
- A power or time above your limits is lowered, not refused.
- Without a pointer or with the switch off, none of these buttons appear and nothing breaks.

## Test without hardware

The adapter conformance kit includes a simulated pointer for developers. See the
[hardware page](../device-adapters/hardware/shelf-pointer.md#testing-without-hardware).
