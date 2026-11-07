---
title: Products, prices and stock
summary: Configure products, variant prices and photos, then record stock through the stock ledger.
order: 20
keywords: products, catalogue, variants, options, size, colour, SKU, barcode, price, discount, photo, stock, reorder, bundle, consumable
modules: shop
---
## Add or edit a product

1. Open **Shop → Catalogue → New product**. Enter its name, kind, category, unit and description.
2. Choose **Show on the public shop page** and **On sale** as appropriate. A desk-only product stays out of public browsing.
3. Add a variant for each sellable size or colour. Each has its own name, SKU or barcode, price, active state and up to three option name/value pairs.
4. Use **Product display order** and the variant's display order to arrange them; lower numbers appear first. Existing positions remain unchanged when you edit other details.
5. Where enabled, configure **Members only**, the per-order maximum, exact public stock, tax rate and HSN code, and the variant's reorder point.
6. Save the product. Reopen the saved product to add, replace or remove its **Product photo**. Variants share that photo.

![Screenshot: a shop product with its variants](screenshot:shop-product)

A category is the label buyers use to filter the shop; it does not require a separate category-creation screen. SKUs must be unique within this shop. Product and variant archiving removes them from sale while keeping their old orders and stock history.

## Prices and member discounts

Enter each variant's normal price. Where tax classes are enabled, prices include tax; the product can specify its rate and a four-to-eight-digit HSN code.

There is no second member-price field on each variant. The Space Manager creates applicable member discounts in **Settings → Pricing → Member discounts** and can scope a rule to **Shop** and **Item price**. Turning on **Member prices** also enables a product's **Members only** control.

The server re-quotes a changed basket before it is placed. Once an order is placed, its quote and receipt snapshots preserve what was sold; editing today's product price does not rewrite old orders.

## Record stock

Open **Shop → Stock**. Each variant shows its on-hand, held and available quantities.

- **Restock** adds what arrived.
- **Adjust → Shelf count** records the counted total as a change from the current balance.
- **Damaged** and **Used in the space** take stock out and require a reason.
- **History** shows the recorded movements.

Stock cannot go below zero or below live holds. A linked inventory consumable uses the inventory's own count; never edit a second independent count for it. A kit in bundle mode takes stock from its chosen component variants.

Public pages show **In stock**, **Low** or **Sold out**. Exact counts require both **Stock on the shop page** and that product's own exact-count option. Internal locations, links to inventory items and other buyers are not public.

> **Who can do this:** the Shop Manager and Space Manager manage products and stock. Staff with Shop view access can read stock history. Member discount rules and finance defaults remain the Space Manager's responsibility.
