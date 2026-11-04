# Analytics views (release 2, lane L25)

**Catalogue version 1.** These are the curated, read-only views a space's analytics database login
(and the platform-wide Metabase login) can read. They are generated from `backend/apps/analytics/catalogue/`;
the module and its switches are described under [analytics](MODULES.md#analytics), the rules under
[Analytics](INVARIANTS.md#per-space-analytics-release-2-lane-l25-163b) in the invariants.

## Where they live

| Schema | Who reads it | Rows | Member names and emails |
| --- | --- | --- | --- |
| `spaceworks_analytics` | the space's own login | that space only, while the `analytics` module is on and the space is active | only in `members`, only when **Show member details** is on |
| `spaceworks_analytics_platform` | the platform login (superadmin) | every space | never |

Every view has a `makerspace_id` column. A person is always named by `member_id` (the same number in every view);
only `members` can turn that number into a name. `views_catalog` lists every view, its domain, the version that
introduced it and the catalogue version.

Nothing here carries a password, token, secret, digest, pickup or claim code, evidence or object key, storage
location, box or QR id, contact field (email, phone, address), free-text note, answer or description, payment
provider reference or checkout URL.

## Versioning

The catalogue version goes up whenever a view or column is added, renamed, removed or changes meaning. Adding is
preferred: removing or renaming a column breaks saved Metabase questions. Each view lists the version that added it.

## Inventory

### `inventory_products` (since 1)

Every catalogue item with its live quantity counts.

| Column | Meaning |
| --- | --- |
| `makerspace_id` | The space the row belongs to. |
| `product_id` | Item id. |
| `category_id` | Category (inventory_categories). |
| `name` | Item name. |
| `manufacturer` | Manufacturer. |
| `model` | Model. |
| `sku` | Stock-keeping code. |
| `tracking_mode` | Quantity or per-asset tracking. |
| `is_consumable` | Used up rather than lent. |
| `total_quantity` | Units in the catalogue. |
| `available_quantity` | Units free to lend now. |
| `reserved_quantity` | Units reserved for accepted requests. |
| `issued_quantity` | Units out on loan. |
| `damaged_quantity` | Units recorded damaged. |
| `lost_quantity` | Units recorded lost. |
| `needs_fix_quantity` | Units waiting for repair. |
| `unit_cost` | Unit cost, if recorded. |
| `cost_currency` | Currency of the unit cost. |
| `deposit_amount` | Deposit asked when lent. |
| `is_public` | Listed in the public catalogue. |
| `is_archived` | Archived item. |
| `created_at` | When the item was added. |

### `inventory_categories` (since 1)

Catalogue categories.

| Column | Meaning |
| --- | --- |
| `makerspace_id` | The space the row belongs to. |
| `category_id` | Category id. |
| `name` | Category name. |
| `loan_days` | Default loan length in days. |
| `max_renewals` | Renewals allowed. |
| `created_at` | When the category was added. |

### `loan_requests` (since 1)

Borrow requests through their lifecycle; the borrower is a member id only.

| Column | Meaning |
| --- | --- |
| `makerspace_id` | The space the row belongs to. |
| `request_id` | Request id. |
| `member_id` | Borrower (members); empty for account-less requests. |
| `status` | Request state. |
| `created_at` | Submitted. |
| `accepted_at` | Accepted. |
| `issued_at` | Handed over. |
| `return_due_at` | Due back. |
| `closed_at` | Closed. |
| `renewal_count` | Renewals taken. |
| `days_out` | Days between hand-over and close (or now). |

### `loan_request_items` (since 1)

The items and quantities of each borrow request.

| Column | Meaning |
| --- | --- |
| `makerspace_id` | The space the row belongs to. |
| `request_item_id` | Line id. |
| `request_id` | Request (loan_requests). |
| `product_id` | Item (inventory_products). |
| `requested_quantity` | Units requested. |
| `accepted_quantity` | Units accepted. |
| `issued_quantity` | Units issued. |
| `returned_quantity` | Units returned. |
| `damaged_quantity` | Units damaged. |
| `missing_quantity` | Units missing. |
| `needs_fix_quantity` | Units needs fix. |

### `tool_loans` (since 1)

Self-checkout and direct-handout loans of QR-tracked tools.

| Column | Meaning |
| --- | --- |
| `makerspace_id` | The space the row belongs to. |
| `tool_loan_id` | Loan id. |
| `member_id` | Borrower (members). |
| `request_id` | Linked request, if any. |
| `target_type` | Item or container. |
| `target_label` | What was lent. |
| `status` | Loan state. |
| `source` | Self-checkout, kiosk or staff handout. |
| `checked_out_at` | Checked out. |
| `due_at` | Due back. |
| `returned_at` | Returned. |

## Machines

### `machines` (since 1)

Every machine with its current status.

| Column | Meaning |
| --- | --- |
| `makerspace_id` | The space the row belongs to. |
| `machine_id` | Machine id. |
| `machine_type_id` | Type (machine_types). |
| `name` | Machine name. |
| `status` | Current status. |
| `status_since` | Since when. |
| `is_public` | Shown on the public page. |
| `is_active` | In use (not retired). |
| `created_at` | Added. |

### `machine_types` (since 1)

Machine types: the space's own and the built-in ones. Lookup view: also lists rows owned by no space (built-in machine types).

| Column | Meaning |
| --- | --- |
| `makerspace_id` | The space the row belongs to. |
| `machine_type_id` | Type id. |
| `slug` | Type key. |
| `name` | Type name. |
| `is_builtin` | Built into SpaceWorks (makerspace_id is empty). |

### `machine_jobs` (since 1)

Machine service jobs (3D prints, laser cuts and others) from request to pickup.

| Column | Meaning |
| --- | --- |
| `makerspace_id` | The space the row belongs to. |
| `job_id` | Job id. |
| `member_id` | Requesting member (members). |
| `queue_id` | Service queue. |
| `assigned_machine_id` | Machine it ran on (machines). |
| `batch_id` | Batch, when started with others. |
| `status` | Job state. |
| `urgent` | Marked urgent. |
| `copies` | Copies asked for. |
| `own_material` | Member brought the material. |
| `prepay` | Paid before the run. |
| `created_at` | When the job was submitted. |
| `queued_at` | When the job was queued. |
| `accepted_at` | When the job was accepted. |
| `started_at` | When the job was started. |
| `completed_at` | When the job was completed. |
| `collected_at` | When the job was collected. |
| `failed_at` | When the job was marked failed. |
| `cancelled_at` | When the job was cancelled. |
| `paid_at` | When the job was paid. |
| `estimated_minutes` | Estimated machine minutes. |
| `actual_minutes` | Measured machine minutes. |
| `planned_grams` | Planned material, grams. |
| `actual_consumed_grams` | Material used, grams. |
| `metering_unit` | Unit for non-gram materials. |
| `actual_consumed_quantity` | Material used in that unit. |
| `payment_amount` | Charge for the job. |
| `payment_status` | Payment state. |
| `fail_code` | Failure reason code. |
| `failure_outcome` | What happened after a failure. |
| `reject_code` | Rejection reason code. |

### `machine_usage` (since 1)

Logged machine time, from jobs and from walk-up use.

| Column | Meaning |
| --- | --- |
| `makerspace_id` | The space the row belongs to. |
| `usage_id` | Entry id. |
| `machine_id` | Machine (machines). |
| `member_id` | Member who used it (members). |
| `job_id` | The job it ran, if any (machine_jobs). |
| `started_at` | Started. |
| `hours` | Hours logged. |
| `duration_minutes` | Minutes logged. |
| `outcome` | Outcome. |
| `source` | How it was logged. |
| `percent_complete` | Progress at the end of a failed run. |
| `consumed_grams` | Material used, grams. |
| `metering_unit` | Unit for non-gram materials. |
| `consumed_quantity` | Material used in that unit. |
| `created_at` | Logged. |

### `machine_downtime` (since 1)

Out-of-service periods per machine.

| Column | Meaning |
| --- | --- |
| `makerspace_id` | The space the row belongs to. |
| `downtime_id` | Period id. |
| `machine_id` | Machine (machines). |
| `kind` | Planned or unplanned. |
| `started_at` | Went down. |
| `ended_at` | Came back (empty while down). |
| `expected_back_at` | Expected back. |
| `minutes` | Minutes down so far. |

## Bookings

### `bookable_spaces` (since 1)

Rooms and resources that can be booked.

| Column | Meaning |
| --- | --- |
| `makerspace_id` | The space the row belongs to. |
| `bookable_space_id` | Resource id. |
| `name` | Resource name. |
| `kind` | Room, desk, machine time and so on. |
| `capacity` | Capacity. |
| `machine_type_id` | Machine type, for machine time (machine_types). |
| `machine_id` | Machine, for machine time (machines). |
| `payment_amount` | Price per booking. |
| `is_public` | Bookable from the public page. |
| `is_active` | Open for booking. |
| `created_at` | Added. |

### `bookings` (since 1)

Bookings with their times and state.

| Column | Meaning |
| --- | --- |
| `makerspace_id` | The space the row belongs to. |
| `booking_id` | Booking id. |
| `bookable_space_id` | Resource (bookable_spaces). |
| `member_id` | Member (members); empty for a guest booking. |
| `status` | Booking state. |
| `starts_at` | Starts. |
| `ends_at` | Ends. |
| `duration_minutes` | Booked minutes. |
| `created_at` | Requested. |
| `cancelled_at` | Cancelled. |
| `arrived_at` | Checked in. |
| `departed_at` | Checked out. |

## Events

### `events` (since 1)

Events with their dates, capacity and price.

| Column | Meaning |
| --- | --- |
| `makerspace_id` | The space the row belongs to. |
| `event_id` | Event id. |
| `series_id` | Series, if part of one. |
| `category_id` | Category. |
| `title` | Event title. |
| `status` | Event state. |
| `starts_at` | Starts. |
| `ends_at` | Ends. |
| `location_kind` | In person, online or hybrid. |
| `delivery_mode` | How it is delivered. |
| `capacity` | Capacity. |
| `payment_amount` | Base price. |
| `is_public` | Public event. |
| `listing` | Listed or unlisted. |
| `requires_approval` | Registrations need approval. |
| `created_at` | Created. |

### `event_registrations` (since 1)

Registrations; the attendee is a member id only.

| Column | Meaning |
| --- | --- |
| `makerspace_id` | The space the row belongs to. |
| `registration_id` | Registration id. |
| `event_id` | Event (events). |
| `member_id` | Member (members). |
| `ticket_type_id` | Ticket type (event_ticket_types). |
| `status` | Registration state. |
| `audience` | Audience it registered under. |
| `quoted_amount` | Price quoted. |
| `discount_amount` | Discount given. |
| `created_at` | Registered. |
| `cancelled_at` | Cancelled. |

### `event_checkins` (since 1)

Attendance records (each check-in at the door or a station).

| Column | Meaning |
| --- | --- |
| `makerspace_id` | The space the row belongs to. |
| `checkin_id` | Check-in id. |
| `event_id` | Event (events). |
| `registration_id` | Registration (event_registrations). |
| `source` | Where it was recorded. |
| `attended_at` | Attended at. |

### `event_applications` (since 1)

Applications to events that admit by application (hackathons and others).

| Column | Meaning |
| --- | --- |
| `makerspace_id` | The space the row belongs to. |
| `application_id` | Application id. |
| `event_id` | Event (events). |
| `member_id` | Applicant (members). |
| `registration_id` | Registration once admitted (event_registrations). |
| `cohort_id` | Cohort. |
| `state` | Application state. |
| `submitted_at` | Submitted. |
| `offered_at` | Offered a place. |
| `response_at` | Applicant responded. |
| `rsvp_accepted_at` | Accepted the offer. |

## Tickets

### `event_ticket_types` (since 1)

Ticket types and their prices.

| Column | Meaning |
| --- | --- |
| `makerspace_id` | The space the row belongs to. |
| `ticket_type_id` | Ticket type id. |
| `event_id` | Event (events). |
| `series_id` | Series, for a series ticket. |
| `name` | Ticket name. |
| `amount` | Price. |
| `pricing_mode` | Fixed or pay-what-you-want. |
| `capacity` | Seats on sale. |
| `is_active` | On sale. |
| `sales_start_at` | Sales open. |
| `sales_end_at` | Sales close. |

### `event_orders` (since 1)

Ticket orders with their totals; the buyer is a member id only.

| Column | Meaning |
| --- | --- |
| `makerspace_id` | The space the row belongs to. |
| `order_id` | Order id. |
| `event_id` | Event (events). |
| `series_id` | Series, for a series pass. |
| `member_id` | Buyer (members). |
| `kind` | Order kind. |
| `status` | Order state. |
| `currency` | Currency. |
| `subtotal` | Before discounts and fees. |
| `discount_total` | Discounts. |
| `fee_total` | Booking fees. |
| `total` | Total. |
| `created_at` | Created. |
| `paid_at` | Paid. |
| `closed_at` | Closed. |

### `event_order_lines` (since 1)

The tickets, add-ons and passes in each order.

| Column | Meaning |
| --- | --- |
| `makerspace_id` | The space the row belongs to. |
| `order_line_id` | Line id. |
| `order_id` | Order (event_orders). |
| `kind` | Ticket, add-on or pass. |
| `ticket_type_id` | Ticket type (event_ticket_types). |
| `addon_id` | Add-on. |
| `pass_type_id` | Series pass type. |
| `label` | Line label. |
| `quantity` | Quantity. |
| `unit_amount` | Frozen unit price. |
| `discount_amount` | Discount on the line. |
| `line_total` | Line total. |

## Membership

### `members` (since 1)

Everyone with a membership in the space, staff and community.

| Column | Meaning |
| --- | --- |
| `makerspace_id` | The space the row belongs to. |
| `member_id` | Person id; the member_id of every other view. |
| `membership_id` | Membership id. |
| `member_number` | Member number. |
| `track` | Community member or staff. |
| `status` | Membership state. |
| `source` | How they joined. |
| `created_at` | Joined. |
| `activated_at` | Activated. |
| `revoked_at` | Revoked. |
| `verified` | Verified by staff. |
| `waiver_accepted` | Signed the waiver. |
| `display_name` | Name (masked unless the space shows member details). **Personal data, masked by default.** |
| `email` | Email (masked unless the space shows member details). **Personal data, masked by default.** |

### `membership_plans` (since 1)

Membership plans and their prices.

| Column | Meaning |
| --- | --- |
| `makerspace_id` | The space the row belongs to. |
| `plan_id` | Plan id. |
| `name` | Plan name. |
| `plan_type` | Plan type. |
| `interval` | Billing interval. |
| `amount` | Price per term. |
| `joining_fee` | Joining fee. |
| `currency` | Currency. |
| `is_active` | Offered. |
| `is_public` | Shown publicly. |
| `created_at` | Created. |

### `membership_terms` (since 1)

Membership terms: who held which plan, when and for how much.

| Column | Meaning |
| --- | --- |
| `makerspace_id` | The space the row belongs to. |
| `term_id` | Term id. |
| `membership_id` | Membership (members). |
| `member_id` | Member (members). |
| `plan_id` | Plan (membership_plans). |
| `kind` | New, renewal and so on. |
| `status` | Term state. |
| `starts_at` | Starts. |
| `ends_at` | Ends. |
| `price` | Frozen price. |
| `joining_fee` | Frozen joining fee. |
| `currency` | Currency. |
| `created_at` | Created. |

## Payments

### `payments` (since 1)

Charges and payments: amount, currency, subject kind and state.

| Column | Meaning |
| --- | --- |
| `makerspace_id` | The space the row belongs to. |
| `payment_id` | Charge id. |
| `subject_type` | What it pays for (loan, booking, event, membership...). |
| `amount` | Amount. |
| `currency` | Currency. |
| `status` | Charge state. |
| `provider` | Offline, unclaimed or the online provider. |
| `online_rail` | Hosted checkout or native sheet. |
| `due_at` | Due. |
| `created_at` | Raised. |
| `updated_at` | Last changed. |

### `finance_ledger` (since 1)

Money in and out from the finance ledger (L5), by domain and category.

| Column | Meaning |
| --- | --- |
| `makerspace_id` | The space the row belongs to. |
| `entry_id` | Entry id. |
| `kind` | Income or expense. |
| `domain` | Area it belongs to. |
| `machine_type_id` | Machine type, for machine money (machine_types). |
| `event_id` | Event, for event money (events). |
| `category` | Category. |
| `method` | Cash, bank, card and so on. |
| `account` | Cash or bank account. |
| `amount` | Amount. |
| `currency` | Currency. |
| `entry_date` | Date of the movement. |
| `source_kind` | What recorded it. |
| `is_void` | Voided entry. |
| `created_at` | Recorded. |

### `refund_cases` (since 1)

Refund cases (staff-approved; nothing is refunded automatically).

| Column | Meaning |
| --- | --- |
| `makerspace_id` | The space the row belongs to. |
| `refund_case_id` | Case id. |
| `payment_id` | Charge (payments). |
| `kind` | Case kind. |
| `area` | Area. |
| `reason_code` | Reason code. |
| `status` | Case state. |
| `due_amount` | Amount the policy says is due. |
| `approved_amount` | Amount staff approved. |
| `created_at` | Opened. |
| `decided_at` | Decided. |

## Procurement

### `to_buy_items` (since 1)

To-Buy entries from request to stock, with costs.

| Column | Meaning |
| --- | --- |
| `makerspace_id` | The space the row belongs to. |
| `to_buy_id` | Entry id. |
| `kind` | Inventory or machine supply. |
| `machine_type_id` | Machine type, for machine supplies (machine_types). |
| `name` | What to buy. |
| `quantity` | Quantity. |
| `status` | Entry state. |
| `estimated_unit_cost` | Estimated unit cost. |
| `actual_unit_cost` | Paid unit cost. |
| `vendor_name` | Vendor (a business, not a person). |
| `created_at` | Added. |
| `ordered_at` | Ordered. |
| `received_at` | Received. |
| `moved_to_inventory_at` | Moved into stock. |

## Pending at merge (not in version 1)

Pre-written in `catalogue/pending_lanes.py`, registered when their lanes merge (catalogue version 2):
donations and sponsors (L18), admission decisions and event crew (L21a), the shop (L22). L24's price-drop refund
cases need no new view: they appear in `refund_cases` with their own `reason_code`.
