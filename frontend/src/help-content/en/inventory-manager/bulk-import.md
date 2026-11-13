---
title: Bulk-import items
summary: Bring a whole inventory list in from a spreadsheet in one go.
order: 80
keywords: bulk import, csv, xlsx, excel, spreadsheet, upload items, paste table, qr code, existing labels
modules: bulk_import
---
1. Open **Bulk import**.
2. Upload a CSV or Excel file, paste a table, or use JSON.
3. Under **Match columns**, tell Space Works which column holds what. Set any column you don't want to **Do not import**.
4. Press **Review** and check the rows.
5. Press **Import**. When you see **Import complete**, press **View inventory →**.

![Screenshot: the Match columns step of a bulk import](screenshot:im-bulk-import)

**Already have QR labels?** Add a **qr_code** column with the value each item's label encodes. The labels work as soon as the import finishes. The review flags a code that appears twice in your file, is already linked to another item, or was revoked, and **Import** stays off until you fix them. Codes go on items tracked by quantity; link labels for individual units from the **Scanner**.

If an import fails, **Review and try again** takes you back to fix the file. Imported items start with the quantities in your file, and every one is recorded in the audit log.

> **Who can do this:** Inventory Managers and the Space Manager.
