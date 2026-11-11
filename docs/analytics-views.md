# Analytics views (release 2, lane L25)

**Catalogue version 3.** These are the curated, read-only views a space's analytics database login
(and the platform-wide Metabase login) can read. They are generated from `backend/apps/analytics/catalogue/`;
the module and its switches are described under [analytics](MODULES.md#analytics), the rules under
[Analytics](INVARIANTS.md#per-space-analytics-release-2-lane-l25-163b) in the invariants.

Step-by-step Metabase setup (run it, create the login, connect, embed): [metabase-setup.md](metabase-setup.md).
Grafana reads the same views with the same login (data source, starter dashboards, embedding):
[grafana-setup.md](grafana-setup.md).

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
| `event_only` | Lendable only through an event context (since 3). |
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

### `application_decisions` (since 2)

Committed admission decisions, per stage.

| Column | Meaning |
| --- | --- |
| `makerspace_id` | The space the row belongs to. |
| `decision_id` | Decision id. |
| `event_id` | Event (events). |
| `application_id` | Application (event_applications). |
| `stage_id` | Admission stage. |
| `outcome` | Offer, waitlist, reject or advance. |
| `reason_code` | Reason code. |
| `batch_state` | Draft, committed or cancelled batch. |
| `sent_at` | Sent to the applicant. |

### `event_crew` (since 2)

Event crew (volunteers, mentors and others); no answers or dietary notes.

| Column | Meaning |
| --- | --- |
| `makerspace_id` | The space the row belongs to. |
| `crew_id` | Crew entry id. |
| `event_id` | Event (events). |
| `member_id` | Crew member (members). |
| `origin` | Signed up or invited. |
| `crew_role` | Role on the crew. |
| `state` | Crew state. |
| `decided_at` | Decided. |
| `created_at` | Joined. |

### `judging_rounds` (since 2)

Judging rounds per event.

| Column | Meaning |
| --- | --- |
| `makerspace_id` | The space the row belongs to. |
| `round_id` | Round id. |
| `event_id` | Event (events). |
| `key` | Round key. |
| `mode` | Scoring mode. |
| `state` | Round state. |
| `visibility` | What judges see. |
| `fresh_eyes` | Judges new to the projects. |
| `advanced_from_id` | Round its finalists came from (judging_rounds). |
| `min_reviews` | Reviews per project. |
| `opens_at` | Opens. |
| `closes_at` | Closes. |

### `finalist_advances` (since 2)

Finalist advances from one round to the next.

| Column | Meaning |
| --- | --- |
| `makerspace_id` | The space the row belongs to. |
| `advance_id` | Advance id. |
| `event_id` | Event (events). |
| `source_round_id` | From round (judging_rounds). |
| `target_round_id` | To round (judging_rounds). |
| `selection` | Top N or hand-picked. |
| `top_n` | N, for a top-N advance. |
| `created_at` | Advanced. |

### `judging_finalists` (since 2)

The projects each advance carried forward.

| Column | Meaning |
| --- | --- |
| `makerspace_id` | The space the row belongs to. |
| `finalist_id` | Finalist id. |
| `advance_id` | Advance (finalist_advances). |
| `snapshot_id` | Submitted project snapshot. |
| `source_rank` | Rank in the source round. |

### `finalist_announcements` (since 2)

When finalists were announced.

| Column | Meaning |
| --- | --- |
| `makerspace_id` | The space the row belongs to. |
| `announcement_id` | Announcement id. |
| `event_id` | Event (events). |
| `advance_id` | Advance (finalist_advances). |
| `published_at` | Published. |

### `hackathon_prizes` (since 2)

Prizes and their money per winner.

| Column | Meaning |
| --- | --- |
| `makerspace_id` | The space the row belongs to. |
| `prize_id` | Prize id. |
| `event_id` | Event (events). |
| `name` | Prize name. |
| `award_count` | Winners. |
| `amount_per_winner` | Money per winner. |

### `prize_payouts` (since 2)

Prize payouts and reversals; the recipient is masked like a name.

| Column | Meaning |
| --- | --- |
| `makerspace_id` | The space the row belongs to. |
| `payout_id` | Payout id. |
| `event_id` | Event (events). |
| `prize_id` | Prize (hackathon_prizes). |
| `recipient_id` | Winner (members); masked unless member details are on. **Personal data, masked by default.** |
| `kind` | Payout or reversal. |
| `amount` | Amount. |
| `currency` | Currency. |
| `method` | How it was paid. |
| `paid_on` | Paid on. |
| `ledger_entry_id` | Ledger entry (finance_ledger). |

### `judge_scores` (since 2)

When judge scores were saved and submitted (no values, no notes).

| Column | Meaning |
| --- | --- |
| `makerspace_id` | The space the row belongs to. |
| `score_id` | Score id. |
| `assignment_id` | Judge assignment. |
| `saved_at` | Last saved. |
| `submitted_at` | Submitted. |

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

## Donations

### `donation_campaigns` (since 2)

Donation campaigns and funds with their goals.

| Column | Meaning |
| --- | --- |
| `makerspace_id` | The space the row belongs to. |
| `campaign_id` | Campaign id. |
| `kind` | Campaign or standing fund. |
| `name` | Campaign name. |
| `goal_amount` | Goal. |
| `currency` | Currency. |
| `starts_at` | Opens. |
| `ends_at` | Closes. |
| `is_active` | Open. |
| `is_public` | Public. |
| `created_at` | Created. |

### `donations` (since 2)

Donations: amount, campaign and state; no donor column at all.

| Column | Meaning |
| --- | --- |
| `makerspace_id` | The space the row belongs to. |
| `donation_id` | Donation id. |
| `campaign_id` | Campaign (donation_campaigns). |
| `pledge_id` | Recurring pledge it came from. |
| `amount` | Amount. |
| `currency` | Currency. |
| `source` | Online, cash and so on. |
| `status` | Donation state. |
| `wants_tax_receipt` | Asked for a tax receipt. |
| `period_start` | Pledge period it pays. |
| `created_at` | Recorded. |
| `paid_at` | Paid. |
| `cancelled_at` | Cancelled. |

### `donation_pledges` (since 2)

Recurring donation pledges.

| Column | Meaning |
| --- | --- |
| `makerspace_id` | The space the row belongs to. |
| `pledge_id` | Pledge id. |
| `campaign_id` | Campaign (donation_campaigns). |
| `amount` | Amount per period. |
| `currency` | Currency. |
| `interval` | Monthly, yearly and so on. |
| `status` | Pledge state. |
| `starts_on` | Starts. |
| `next_due_on` | Next due. |
| `ends_on` | Ends. |
| `created_at` | Created. |
| `cancelled_at` | Cancelled. |

### `donation_settings` (since 2)

The space's donation page settings (amounts only).

| Column | Meaning |
| --- | --- |
| `makerspace_id` | The space the row belongs to. |
| `minimum_amount` | Minimum gift. |
| `tax_exempt_valid_until` | Tax-exemption registration valid until. |
| `updated_at` | Last changed. |

### `sponsor_tiers` (since 2)

Sponsor tiers and their prices.

| Column | Meaning |
| --- | --- |
| `makerspace_id` | The space the row belongs to. |
| `tier_id` | Tier id. |
| `name` | Tier name. |
| `rank` | Order. |
| `amount` | Price. |
| `currency` | Currency. |
| `created_at` | Created. |

### `sponsors` (since 2)

Sponsors (organisations) with their tier and term; no contact details.

| Column | Meaning |
| --- | --- |
| `makerspace_id` | The space the row belongs to. |
| `sponsor_id` | Sponsor id. |
| `name` | Sponsor (an organisation) name. |
| `organization_id` | Linked organisation. |
| `tier_id` | Tier (sponsor_tiers). |
| `starts_on` | Sponsorship starts. |
| `ends_on` | Sponsorship ends. |
| `show_on_wall` | Shown on the sponsor wall. |
| `created_at` | Added. |
| `archived_at` | Archived. |

### `sponsor_perks` (since 2)

Perks owed to sponsors and whether they were delivered.

| Column | Meaning |
| --- | --- |
| `makerspace_id` | The space the row belongs to. |
| `perk_id` | Perk id. |
| `tier_id` | Tier template (sponsor_tiers). |
| `sponsor_id` | Sponsor (sponsors). |
| `due_on` | Due. |
| `fulfilled_at` | Delivered. |
| `created_at` | Created. |

### `sponsorship_charges` (since 2)

Charges raised to sponsors.

| Column | Meaning |
| --- | --- |
| `makerspace_id` | The space the row belongs to. |
| `sponsorship_charge_id` | Charge id. |
| `sponsor_id` | Sponsor (sponsors). |
| `amount` | Amount. |
| `currency` | Currency. |
| `created_at` | Raised. |

### `sponsor_event_links` (since 2)

Which sponsors back which events.

| Column | Meaning |
| --- | --- |
| `makerspace_id` | The space the row belongs to. |
| `link_id` | Link id. |
| `sponsor_id` | Sponsor (sponsors). |
| `event_sponsor_id` | The event's sponsor entry. |
| `created_at` | Linked. |

## Shop

### `shop_products` (since 2)

Shop products.

| Column | Meaning |
| --- | --- |
| `makerspace_id` | The space the row belongs to. |
| `shop_product_id` | Product id. |
| `kind` | Product kind. |
| `name` | Product name. |
| `category` | Category. |
| `members_only` | Members only. |
| `is_public` | Public. |
| `is_active` | On sale. |
| `created_at` | Added. |
| `archived_at` | Archived. |

### `shop_variants` (since 2)

Shop variants with price and stock.

| Column | Meaning |
| --- | --- |
| `makerspace_id` | The space the row belongs to. |
| `shop_variant_id` | Variant id. |
| `shop_product_id` | Product (shop_products). |
| `name` | Variant name. |
| `sku` | Stock-keeping code. |
| `price` | Price. |
| `on_hand` | Units on hand. |
| `held` | Units held for open orders. |
| `reorder_point` | Reorder point. |
| `is_active` | On sale. |

### `shop_orders` (since 2)

Shop orders; the buyer is a member id only.

| Column | Meaning |
| --- | --- |
| `makerspace_id` | The space the row belongs to. |
| `shop_order_id` | Order id. |
| `channel` | Online or desk (point of sale). |
| `status` | Order state. |
| `member_id` | Buyer with an account (members); masked unless member details are on. **Personal data, masked by default.** |
| `pickup_at` | Pickup place. |
| `currency` | Currency. |
| `subtotal` | Before discounts. |
| `discount_total` | Discounts. |
| `tax_total` | Tax. |
| `total` | Total. |
| `created_at` | Created. |
| `paid_at` | Paid. |
| `collected_at` | Collected. |
| `closed_at` | Closed. |
| `close_reason` | Why it closed. |

### `shop_order_lines` (since 2)

The variants and quantities of each shop order.

| Column | Meaning |
| --- | --- |
| `makerspace_id` | The space the row belongs to. |
| `shop_order_line_id` | Line id. |
| `shop_order_id` | Order (shop_orders). |
| `shop_variant_id` | Variant (shop_variants). |
| `quantity` | Quantity. |
| `unit_amount` | Unit price. |
| `discount_amount` | Discount. |
| `tax_amount` | Tax. |
| `line_total` | Line total. |

### `shop_returns` (since 2)

Returned shop items and the refund cases they opened.

| Column | Meaning |
| --- | --- |
| `makerspace_id` | The space the row belongs to. |
| `shop_return_id` | Return id. |
| `shop_order_id` | Order (shop_orders). |
| `quantity` | Units returned. |
| `disposition` | Restocked, written off and so on. |
| `amount` | Amount. |
| `refund_case_id` | Refund case (refund_cases). |
| `created_at` | Recorded. |

### `shop_stock_movements` (since 2)

Stock movements per variant (no reason text, no actor).

| Column | Meaning |
| --- | --- |
| `makerspace_id` | The space the row belongs to. |
| `movement_id` | Movement id. |
| `shop_variant_id` | Variant (shop_variants). |
| `kind` | Sale, restock, return, adjustment and so on. |
| `quantity` | Units (negative leaves stock). |
| `balance_after` | Stock after the movement. |
| `shop_order_id` | Order, if any (shop_orders). |
| `created_at` | Recorded. |

### `shop_checkout_holds` (since 2)

Stock held for open orders, and why each hold ended.

| Column | Meaning |
| --- | --- |
| `makerspace_id` | The space the row belongs to. |
| `hold_id` | Hold id. |
| `shop_order_id` | Order (shop_orders). |
| `shop_variant_id` | Variant (shop_variants). |
| `quantity` | Units held. |
| `expires_at` | Hold expires. |
| `released_at` | Released. |
| `release_reason` | Paid, expired or cancelled. |
| `created_at` | Placed. |

### `shop_cash_sessions` (since 2)

Desk cash sessions: amounts and times only.

| Column | Meaning |
| --- | --- |
| `makerspace_id` | The space the row belongs to. |
| `cash_shift_id` | Cash session (shift) id. |
| `status` | Open, closing or closed. |
| `currency` | Currency. |
| `opening_float` | Float at opening. |
| `expected_cash` | Cash expected at close. |
| `counted_cash` | Cash counted at close. |
| `variance` | Counted minus expected. |
| `opened_at` | Opened. |
| `closed_at` | Closed. |

L24's price-drop refund cases need no new view: they appear in `refund_cases` with their own `reason_code`.

## Release 0.12: loan contexts and included hours

### `loan_event_contexts` (since 3)

Borrow requests lent for an event (event equipment, including event-only items).

| Column | Meaning |
| --- | --- |
| `makerspace_id` | The space the row belongs to. |
| `request_id` | Request (loan_requests). |
| `event_id` | Event (events); empty once the link is cleared. |
| `participant_registration_id` | Participant registration (event_registrations), when lent to one participant. |
| `active` | True while the request is lent for this context. |
| `revision` | Context revision counter. |
| `created_at` | Created. |
| `updated_at` | Last changed. |

### `loan_booking_contexts` (since 3)

Borrow requests lent for a room or machine booking.

| Column | Meaning |
| --- | --- |
| `makerspace_id` | The space the row belongs to. |
| `request_id` | Request (loan_requests). |
| `booking_id` | Booking (bookings); empty once the link is cleared. |
| `active` | True while the request is lent for this context. |
| `revision` | Context revision counter. |
| `created_at` | Created. |
| `updated_at` | Last changed. |

### `included_hours_usage` (since 3)

Insert-only ledger of membership-plan included booking hours: consumed and reversed minutes per term.

| Column | Meaning |
| --- | --- |
| `makerspace_id` | The space the row belongs to. |
| `usage_id` | Ledger row id. |
| `term_id` | Membership term (membership_terms). |
| `booking_id` | Booking (bookings). |
| `member_id` | Member who booked (members). |
| `kind` | Room booking or machine time. |
| `entry` | Consumed, or reversed after a rejection or cancellation. |
| `minutes` | Included minutes consumed or given back. |
| `signed_minutes` | Minutes with sign: consumed positive, reversed negative; sum for net usage. |
| `generation` | Consumption generation for a restored booking. |
| `reverses_id` | The consume row this row undoes. |
| `created_at` | Recorded. |

## Release 0.12: guest passes, inductions and incidents

### `day_pass_products` (since 3)

Day passes a space sells.

| Column | Meaning |
| --- | --- |
| `makerspace_id` | The space the row belongs to. |
| `day_pass_product_id` | Product id. |
| `name` | Product name. |
| `amount` | Price. |
| `currency` | Currency of the price. |
| `daily_cap` | Passes sold per day, if capped. |
| `is_public` | Offered on the public page. |
| `is_active` | On sale. |
| `archived_at` | Archived. |
| `created_at` | Added. |

### `guest_passes` (since 3)

Dated guest permits (event, sponsored, day). Not memberships; never counted as members.

| Column | Meaning |
| --- | --- |
| `makerspace_id` | The space the row belongs to. |
| `pass_id` | Pass id. |
| `member_id` | Holder (a person id; not a roster member). |
| `sponsor_member_id` | Sponsoring member (members). |
| `kind` | Event guest, sponsored guest or day pass. |
| `status` | Pass state. |
| `valid_from` | Valid from. |
| `valid_until` | Valid until. |
| `pass_date` | Local calendar day of the pass. |
| `day_pass_product_id` | Day pass product (day_pass_products). |
| `borrow_mode` | Borrowing the pass allows. |
| `machine_mode` | Machine use the pass allows. |
| `waiver_accepted` | A waiver was accepted. |
| `waiver_accepted_at` | Waiver accepted. |
| `revoked_at` | Revoked. |
| `converted` | Converted to a membership. |
| `created_at` | Issued. |

### `guest_certification_grants` (since 3)

Certifications granted to guests, for example through an induction event.

| Column | Meaning |
| --- | --- |
| `makerspace_id` | The space the row belongs to. |
| `grant_id` | Grant id. |
| `certification_type_id` | Certification type. |
| `member_id` | Guest (a person id; not a roster member). |
| `source_event_id` | Induction event (events). |
| `granted_at` | Granted. |
| `expires_at` | Expires. |
| `revoked_at` | Revoked. |

### `incidents` (since 3)

Safety incident and near-miss register: kind, severity, state and links, never the text.

| Column | Meaning |
| --- | --- |
| `makerspace_id` | The space the row belongs to. |
| `incident_id` | Incident id. |
| `kind` | Incident or near miss. |
| `severity` | Severity. |
| `status` | State. |
| `area` | Area of the space it concerns. |
| `occurred_at` | Happened. |
| `reporter_member_id` | Reporter (members). |
| `involved_member_id` | Person involved (members). |
| `machine_id` | Machine (machines). |
| `bookable_space_id` | Room (bookable_spaces). |
| `event_id` | Event (events). |
| `request_id` | Loan request (loan_requests). |
| `booking_id` | Booking (bookings). |
| `pass_id` | Guest pass (guest_passes.pass_id). |
| `closed_at` | Closed. |
| `created_at` | Recorded. |

### `incident_actions` (since 3)

Follow-up actions on incidents; counts and timing, not text.

| Column | Meaning |
| --- | --- |
| `makerspace_id` | The space the row belongs to. |
| `action_id` | Action id. |
| `incident_id` | Incident (incidents). |
| `assignee_member_id` | Assignee (members). |
| `due_date` | Due. |
| `done_at` | Done. |
| `created_at` | Created. |

## Where cost and usage figures come from

- **Price basis.** Products and consumable pools each carry an optional current price (`unit_cost`,
  `cost_currency`, `cost_unit`), entered as a major-currency amount per cost unit. Recorded consumption
  stores the resulting cost in minor units at the time it is logged, so later price edits never rewrite
  history. Consumption with no price basis (for example grams drawn from a pool that has no price) stays
  "cost unknown" rather than being valued at zero.
- **Who used a machine.** A machine usage entry can name the member who used it and when they started
  (`member_id`, `started_at`). Entries are append-only; correcting one is done with a new entry.
- **Delivery facts.** Email, SMS and push delivery outcomes (provider source, bounce and complaint times)
  describe the message, not the person. Provider message ids are removed from an email log row when the
  recipient's account is purged; the remaining outcome facts are kept.
- **Daily facts.** Machine status changes and daily stock snapshots (available, issued, total, out of
  stock, below reorder point) hold no person.
