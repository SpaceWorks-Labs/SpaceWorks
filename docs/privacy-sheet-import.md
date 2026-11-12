# Google Sheets import privacy note

Staff can import members, or people into an ID programme, from a Google Sheet instead of a file. This
is off until a Space Manager turns on **Member import from Google Sheets** or **ID-programme import from
Google Sheets** for the space.

What SpaceWorks does with the sheet:

- **It reads only sheets shared as "Anyone with the link can view".** SpaceWorks never signs in to
  Google, never asks for a Google account or permission, and cannot read a private sheet.
- **It fetches the sheet from Google directly**, as a CSV export of one tab, when staff press Preview
  and again when they import. Google sees a request from the SpaceWorks server for that sheet, as it
  would from any browser with the link.
- **It keeps no copy.** The rows are read for that one request, exactly like an uploaded file, and
  then discarded. The import keeps only its counts and the fact that the rows came from a Google Sheet
  (an ID-programme import also keeps a fingerprint of the content, as it does for a file); the link
  itself is never stored or written to the audit log or the server logs.
- **The people in the sheet are treated as in any import.** Each row becomes a pending
  entry with an emailed invitation; nobody is linked to an existing account and no account is created
  until the person accepts by signing in with that verified email.

To stop SpaceWorks reading a sheet, turn the switch off or change the sheet's sharing back to
restricted. Anyone you gave the link to can still read a link-shared sheet; share only what the import
needs.
