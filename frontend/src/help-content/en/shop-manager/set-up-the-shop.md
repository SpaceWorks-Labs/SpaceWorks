---
title: Set up the shop
summary: Choose Shop features, policies and access, then prepare the catalogue and stock.
order: 10
keywords: shop, setup, shop manager, features, holds, returns, pickup, policy, member prices, tax, settings locks
modules: shop
---
Each makerspace has its own pickup-only shop for kits, consumables and merchandise.

## Open the shop

1. The Space Manager opens **Settings → Modules** and turns on **Shop**.
2. The Space Manager enables **Track money owed** and **Track shop sales** under Features. With shop sales tracking off, buyers may browse but cannot place orders and the till cannot sell.
3. Give the person running the shop the **Shop Manager** role under **Staff & roles**.
4. Open **Shop → Settings** to choose the shop features and policies below. Add products under **Catalogue**, then record stock under **Stock**.

![Screenshot: the shop features under Features](screenshot:shop-features)

## Shop features

Each switch keeps existing records when turned off. The Space Manager can lock a switch for Shop Managers; the lock and read-only state appear beside it.

| Switch | What it enables |
| --- | --- |
| Online shop | New orders from the public shop page |
| Guest checkout | Buyers without an account, after an emailed verification code |
| Stock holds at checkout | Reserve stock while an order waits for payment |
| Member prices | Member-only products and applicable member discounts |
| Shop tax classes | A product tax rate and HSN code; prices include tax |
| Returns and refunds | Record returned items and open a refund case |
| Cash-up | Open, count and close the cash drawer |
| Pickup at events | Let a buyer choose an eligible event as the pickup place |
| Per-order limits | A product's maximum quantity per order |
| Stock on the shop page | Allow an individual product to show its exact stock |
| Shop receipts | Print or email an order receipt |
| Low-stock reorder | Variant reorder points and low-stock suggestions |
| Kit bundles | Sell a kit by taking stock from its component variants |
| Sell inventory consumables | Link a variant to a consumable in the makerspace inventory |

Turning off **Sell inventory consumables** stops new sales of linked variants and bundles that depend on them. Existing paid orders, holds, returns and stored links remain intact. Lendable tools cannot be sold through this link.

## Holds, returns and collection policies

| Setting | Default | Allowed value |
| --- | --- | --- |
| Online hold | 15 minutes | 5–120 minutes |
| Pay-at-desk hold | 48 hours | 1–720 hours |
| Returns window | 14 days after payment | 0–365 days; zero means no returns |
| First pickup reminder | 3 days after ready | 1–90 days |
| Second pickup reminder | 7 days after ready | 1–180 days, after the first reminder |
| Cancel uncollected after | 30 days | 1–365 days |
| Pickup note | Empty | Up to 300 characters: where and when buyers collect |
| Shop policy | Empty | Up to 2,000 characters, shown before ordering and paying |

**Save settings** saves only the editable values you changed. A locked value stays read-only for a Shop Manager; the Space Manager can change it and release the lock. The backend checks these permissions again before saving.

## Prices, discounts and payments

Set each variant's normal price in **Catalogue**. Member discounts are managed by the Space Manager in **Settings → Pricing → Member discounts**; choose **Shop** as the area for a Shop-only discount. The shop uses its variant prices and has no separate rate-card tab.

Online payment additionally needs the Payments module, configured gateway credentials and Shop online-payment permission. These finance controls belong to the Space Manager. Without an online gateway, the ledger still records what is owed and staff can take payment at the desk.

See [Products, prices and stock](help:shop-manager/products-and-stock), [Front-desk sales](help:shop-manager/front-desk-sales), and [Orders, pickups and returns](help:shop-manager/orders-and-returns).

> **Who can do this:** the Space Manager installs Shop, enables sales tracking, manages finance controls and assigns roles. A Shop Manager controls Shop's own settings and features unless the Space Manager locks them.
