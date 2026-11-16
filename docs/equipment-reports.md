# Equipment reports

Equipment reports use loans that have a recorded issue time. They include items still out, partial returns, completed returns and loans closed with an issue. Draft, pending, accepted but never issued, rejected, cancelled and expired requests are excluded.

The selected period follows the issue time in the makerspace's timezone. The reports show each loan's current status and current links; they do not reconstruct what its links were on a past date.

## Loans by purpose

The summary distinguishes ordinary loans, event loans, booking loans and loans linked to both. Each underlying loan counts once, including self-checkout and staff direct handouts. Multiple item lines do not create extra loans.

Those purpose categories are available only when both contextual modules are enabled and the reader has makerspace-wide event and booking authority. Otherwise all authorized loans appear under **Context not shown**. This means the connection cannot be disclosed; it does not mean there are no event or booking links. The preview also states whether the context dimensions are available.

Turning off an event or booking module does not return equipment, clear the borrower or settle a charge. Ordinary Inventory loans remain independent, subject to their own settings and permissions.

## One event or booking

Open **View equipment report** in an event’s overview or on the exact reservation row in **Bookings**. The preview offers a CSV download after it loads. These entry points require Reports and the source module to be enabled.

The event report lists loans currently linked to that exact event. The booking report uses a specific reservation, rather than every reservation for the same room or machine. A loan linked to both can appear in both detail views, so do not add those two lists to calculate an overall total.

These detail views require inventory and audit access, the relevant loan-source permission, and access to the selected event or booking space. A link grants no additional role. The reports omit borrower contact details, participant identifiers, QR codes, evidence photos and private notes.

## Downloads

CSV and spreadsheet downloads use the same authorized loan cohort and declared columns. Their provenance identifies the report, version, period, subject filter and generator. Preview metadata is not an additional exported data column. When a purpose cannot be disclosed, populated summary rows retain the **Context not shown** label; an empty download contains its column headers and provenance only.

These reports count physical loans. They do not calculate stock availability, consumable usage, repair costs or payment totals. Those figures remain in their respective reports, with money separated by currency.
