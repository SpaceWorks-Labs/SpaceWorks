---
title: QR labels and the scanner
summary: Print QR labels in batches, reprint a lost one, scan to find anything, and revoke a label.
order: 50
keywords: qr, labels, print, batch, reprint, scanner, scan, revoke, sticker, asset, external, existing labels, migrate
---
## Print labels

1. Open **QR Tools** (the page is **QR labels**) and press **New batch**.
2. Give it a title, a label type and a prefix. Press **Create batch**.
3. Press **Add labels**, pick an item and how many units.
4. Press **Download all (ZIP)** and print.

![Screenshot: a QR print batch with labels added](screenshot:im-qr-batch)

**Reprint a unit** prints a new label for a unit that already exists.

## Scan

1. Open **Scanner** and scan any label.
2. You see the box, item or unit it belongs to. **View contents** lists what's in a box.
3. If a label is lost or copied, press **Revoke QR** and confirm. Print a replacement.

A revoked label stops working everywhere at once.

## Use labels you already have

If your tools already carry unique QR labels from another system, you don't need to reprint them.

1. Open **Scanner** and scan the label. Space Works says the code isn't linked to anything yet.
2. Press **Create new item** to add the item now (the code is linked when you save it), or **Link to existing item**, pick the item or unit, and press **Confirm link**.

A code that is already linked shows the item it belongs to and keeps that link. A revoked code can't be linked again. To link many labels at once, add a **qr_code** column to a bulk import.

> **Who can do this:** staff with the QR action (Inventory Manager, Space Manager).
