---
title: Set up SMS and WhatsApp
group: How-to guides
order: 45
summary: Add Twilio SMS or Twilio/Meta WhatsApp as a personal notification channel and understand consent.
---

# Set up SMS and WhatsApp

SMS (Twilio) and WhatsApp (Twilio or Meta Cloud API) deliver **personal** messages to people who have opted in. Each is its own add-on, switched off by default, and enabling the add-on alone never starts sending.

> **Warning** Sending needs all of these at once: the add-on on, a configured sender, a template or session window (WhatsApp), the person's explicit consent, and no suppression. A missing piece means the message is held or skipped, not sent.

## Before you start

- The **SMS** and/or **WhatsApp** add-on is on for the space (**Areas & add-ons**).
- You are a Space Manager.
- For a self-hosted server, `MESSAGING_WEBHOOK_BASE_URL` is set to the exact public origin of the API (no `/api/v1`, query or fragment). Twilio validates signatures against this URL.

## SMS with Twilio

1. Buy an SMS-capable **notification** number in Twilio. Keep it separate from any number used for sign-in codes: provider STOP replies must never disable login or recovery.
2. Open **Settings > Communication > Communication channels > SMS**. Enter the **Account SID**, **Auth token** and **Sender phone number** (E.164, such as `+14155550100`).
3. In Twilio, point the number's inbound and status callbacks at the URLs the settings page displays, and enable Advanced Opt-Out so STOP requests reach SpaceWorks.
4. Save, then press **Send a test**.

## WhatsApp

1. Choose a provider in the **WhatsApp** section: **Twilio** or **Meta WhatsApp Cloud**.
2. Twilio: enter Account SID, Auth token, the public callback base URL (the API's HTTPS origin, no path) and either a WhatsApp sender or a Messaging Service SID.
3. Meta: enter App ID, App secret, WhatsApp Business Account ID, a permanent access token and a webhook verify token. Register the phone number in Meta first; saving settings does not register it.
4. Register the callback URLs the page displays with the provider.
5. Refresh template approvals. Outside the 24-hour reply window (which only an inbound message from the person opens), only approved templates are sent.

## Consent

- Members opt in under their account **Channels** page. SMS needs a verified phone and explicit consent for that space; verifying a phone alone does not subscribe anyone.
- WhatsApp is linked by a signed challenge; a typed number is only a candidate until proven.
- STOP, START or YES typed at the provider never subscribes a person. Only in-app consent does.

## Limits and diagnostics

- On a managed platform the defaults are 100 SMS and 100 WhatsApp messages per space per day; self-hosted servers bypass those quotas. You can also set your own **Messages per day** and **Messages per person per day** on each channel.
- **Settings > Communication > Communication channels** shows a delivery log. "Accepted" is not proof of delivery; delivered and read evidence is recorded separately.

## Platform accounts

A platform operator can supply shared SMS, WhatsApp and push accounts under **Platform settings > Communication > Messaging providers**. A space uses them only when it ticks **Allow the operator's platform sender**. Own credentials always take precedence, and incomplete own credentials refuse delivery instead of falling back.

## See also

- [SMS and WhatsApp notifications](../messaging-channels.md) for callbacks, recovery and retention.
- [Notifications v2](../notification-contract.md)
