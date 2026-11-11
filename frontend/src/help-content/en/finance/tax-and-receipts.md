---
title: Tax, receipts and disputes
summary: Set up tax (including India GST), configure receipt documents, and handle disputes and unexpected payments.
order: 40
keywords: tax, gst, gstin, invoice, receipt, credit note, documents, dispute, chargeback, unexpected payment, upi claim
---
## Tax

1. Open **Settings**, then **Money**, then **Tax**.
2. Under **How you charge tax**, choose **No tax**, **One named tax** or **India GST**.
3. For GST, fill in your GSTIN, service code, scheme and number prefixes.
4. Press **Save tax settings**.

![Screenshot: the Tax settings](screenshot:fin-tax)

Tax applies to charges raised from then on; earlier charges keep what they had.

## Receipt documents

Under **Payments**, **Billing documents**, press **Configure documents** to set your number prefixes, issuer name and address, and the UPI ID used for UPI payments. Receipts and credit notes are then numbered and issued automatically.

### Receipt numbers per financial year

When **Receipt numbers per financial year** is on (**Settings**, **Payments & billing**), receipts are numbered per financial year even if you charge no tax, for example `R26-27/0001`, starting again at `0001` each year. The prefix is your receipt prefix when it is up to four capital letters, digits, `-` or `/`; otherwise `R`. The day you turn it on is the cut-over: receipts already issued keep their numbers.

### A SAC code per membership plan

With **SAC code per membership plan** and GST on, each membership plan has an optional **SAC code** (4 to 8 digits). A term on that plan prints its code on the GST invoice; a blank code uses the space-wide one. Charges already raised keep the code they had.

## Payers who say they've paid

Where UPI claims are on, **Finance**, **Offline payments**, **Payers say they paid** lists claims with a transaction reference. Check the money reached your account, then **Confirm payment** or **Not received**.

## Disputes and unexpected payments

- **Disputes** lists card chargebacks. Respond in your payment provider's dashboard; Space Works records them.
- **Unexpected payments** holds late, duplicate or mismatched online payments: **Issue receipt on what arrived**, **Open a refund case** or **Note what happened**.

> **Who can do this:** tax and document settings are the Space Manager's alone; finance staff handle claims, disputes and flags.
