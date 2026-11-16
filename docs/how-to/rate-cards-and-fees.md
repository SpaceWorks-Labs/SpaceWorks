---
title: Set prices, rate cards and fees
group: How-to guides
order: 150
summary: Decide per area whether the space charges nothing, records debts to settle offline, or takes online payment, then set rates.
---

# Set prices, rate cards and fees

Every area (Inventory, Machines, Bookings, Events, Membership) can be **free**, **paid offline** or **paid online**, independently. One pattern prices everything: rate card, then item price, then loan waiver, then member discount, then a frozen quote that becomes a payment record.

## Before you start

- You are the Space Manager. Pricing is a finance setting.
- Decide the money mode for each area:

| Mode | Behaviour |
| --- | --- |
| Free | Nothing is recorded; no price is shown |
| Paid offline | The debt is recorded and staff settle it with a receipt (method, reference, date) |
| Paid online | As offline, plus a payment rail (Stripe or Razorpay) for checkout |

Recording what is owed needs no payment provider. Online checkout needs the **Payments** add-on and provider credentials (**Settings > Money > Payments & billing**).

## Steps

1. Open **Settings > Features** and make sure **charges** and **pricing** (`charges.enabled`, `charges.pricing`) are on, along with the area's own charge switch (for example `charges.loans`).
2. Open **Settings > Money > Pricing**. There is one tab per area.
3. Set the rate card for the area:

| Area | Components |
| --- | --- |
| Inventory | Rental per loan or per day (with a cap), refundable deposit, late fee per day (cap and grace), damage, lost |
| Machines | Time per hour (billing increment and minimum), material per unit, per job |
| Bookings | Per booking, per hour (rounded up to the increment, capped per day) |
| Events | Per registration (the default only prefills new events) |
| Membership | Read-only here: plans own their prices |

4. Before saving a default, read the **impact preview**: it lists every item whose price would move.
5. For one item, machine, material or room, set its own price to **Inherit**, **Free** or **Custom**. Zero or empty means inherit the default.
6. For loans, choose when rental is charged: **at checkout** (planned days) or **at return** (actual days). The choice made when a loan is issued sticks to that loan.
7. Optional: switch on **discounts** (`charges.discounts`) for all members, one plan's members or one member. The single best automatic rule applies, then an event promo code.
8. Set taxes under **Settings > Money > Payments & billing**.

## Waive fees

With `loans.fee_waivers` on, staff who can take returns waive a loan's rental, late, damage or lost fee with a recorded reason. A fee already paid opens a refund case for approval. The deposit is never waived.

## Good to know

- A price of 0 raises no payment and is audited as `charge.free_by_pricing`.
- A booking awaiting approval keeps the price quoted when it was requested. A machine session keeps the price shown at Start.
- Rounding is half-up to each currency's precision (no decimals for yen; three decimals for KWD, BHD, OMR, JOD and TND).
- A restricted member can still pay an outstanding charge.

> **Tip** Start with everything free, record a few loans, then add a rate card to one area. The default for a new component is free, so nothing changes until you save a rate.

## See also

- [Payments and billing](../payment-billing.md#pricing-paid-and-free-everywhere) for quotes, refunds and receipts.
- [Loan policy](../loan-policy.md)
