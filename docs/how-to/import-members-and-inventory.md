---
title: Import members and inventory from a spreadsheet
group: How-to guides
order: 90
summary: Bring members and inventory in from CSV, TSV or Excel, preview every change first and review the result.
---

# Import members and inventory from a spreadsheet

Both imports are wizards that **preview before they change anything**. Neither deletes existing records.

## Import members

Needs the **Membership** area on and its **Import** capability switched on (**Settings > Areas > Features**).

1. Open the **Members** area, go to the **Import** tab and press **Import members**.
2. Choose a file: CSV, TSV or Excel (`.xlsx`), up to 5 MB and 5,000 rows. The first row holds the column names. Alternatively paste a Google Sheets link (see below).
3. Press **Preview**. Match your columns to SpaceWorks fields if the names differ, then **Check again with these columns**.
4. Read the dry run: it counts rows as new, updated or skipped, and gives a reason for each skip (email missing or invalid, start or end date not understood, plan name not found, email or phone repeated, member number already used, already an active member).
5. Tick **Record only** on rows that should be saved without sending an invitation, or **Skip** on rows to leave out.
6. Press **Import**, then **Download result CSV** to keep the outcome.

> **Note** Each person becomes a **pending membership** with an emailed invitation, and joins by signing in with that verified email. Nobody is linked to an existing account on their behalf, and no account is created until they accept.

### From a Google Sheet

The **Member import from Google Sheets** switch (`membership.import_sheets`) allows pasting a link instead of uploading a file. The sheet must be shared as "Anyone with the link can view". SpaceWorks never signs in to Google, fetches one tab as CSV for each preview and import, and keeps no copy; the link is never stored or logged. See [the privacy note](../privacy-sheet-import.md).

## Import inventory

1. Open **Bulk import** (`/admin/bulk-import`) in the inventory console.
2. Upload a CSV, TSV or XLSX file. The wizard steps are **Upload**, **Match columns**, **Review**, **Import**.
3. Review every change. Rows with problems are listed; you can import the valid rows and skip the rest.
4. If your file carries QR codes, fix any QR problems and preview again: QR codes are never skipped or reassigned.
5. When the import finishes, open the inventory to review it.

> **Tip** Import a handful of rows first. The review step is cheap; fixing hundreds of wrong rows afterwards is not.

## Other imports

- **Whole spaces** between servers use [tenant migration](move-a-space.md), not these wizards.
- **ID programmes** can import people from a CSV (up to 2 MB, UTF-8) or a public Google Sheet in the programme's page.

## See also

- [Choosing modules](../choosing-modules.md)
- [Export your data](export-your-data.md)
