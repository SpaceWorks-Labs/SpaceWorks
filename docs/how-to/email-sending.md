---
title: Send email through your own provider
group: How-to guides
order: 20
summary: Choose SMTP or an email API provider for a space, and understand what falls back to the platform sender.
---

# Send email through your own provider

A space can send its notification email from its own address through SMTP or one of several email API providers. If you set nothing, the space inherits the platform's sender.

> **Note** Password resets, sign-in codes and other authentication mail always use the **platform** email configuration, never a space's own. A space's provider covers that space's notifications only.

## Before you start

- The **Email** add-on is on for the space (**Areas & add-ons**). The **Email sending** page only appears while it is on.
- You have an account with a provider and a sender address that provider has verified.

## Set up a space's sender

1. Open **Settings > Communication > Email sending**.
2. Under **Email delivery**, pick a provider: **Inherit platform email**, **SMTP**, **Resend**, **Postmark**, **Amazon SES (HTTP)**, **Brevo**, **Mailgun** or **SendGrid**.
3. Enter the **From email**. Use an address the provider has verified.
4. Fill in the provider's fields:

| Provider | You enter |
| --- | --- |
| SMTP | Host, port, username, password; then either STARTTLS (port 587) or implicit SSL (port 465), not both |
| Resend, Brevo, SendGrid | API key |
| Postmark | Server token |
| Mailgun | API key, sending domain, region (`us` or `eu`) |
| Amazon SES | Region, a dedicated AWS access key ID and secret (a session token is optional), or "workload identity" instead of keys |

5. Save. Secrets are stored encrypted and never shown again: leave a field blank later to keep what is saved, or fill every required field to replace it.
6. On the same page choose which managers receive hardware and print lifecycle emails under **Notification recipients**.

> **Tip** To check that mail leaves the building, use **Settings > Communication > Email logs** after triggering a notification.

## Platform sender (superadmin)

The platform superadmin sets the default under **Platform settings > Communication > Email**. A self-hosted server can also set it in `.env`:

```env
EMAIL_HOST=smtp.example.org
EMAIL_PORT=587
EMAIL_HOST_USER=apikey
EMAIL_HOST_PASSWORD=...
EMAIL_USE_TLS=true
DEFAULT_FROM_EMAIL="Example Space <noreply@example.org>"
```

Alternatively set `EMAIL_PROVIDER` and `EMAIL_PROVIDER_CONFIG_FILE` to use an API provider instead of SMTP. The full list is in the [environment reference](../environment-reference.md).

## Sender name, reply-to and the SMTP test

- A space can set a **sender name** and a **reply-to address** (Settings > Email). Mail from the space then shows that name and replies go to that address; the From address itself does not change. Turn this off with the `email.sender_identity` switch.
- A space's **own SMTP account is used only after it passes a test**. Choose **Send test message** (`POST /api/v1/admin/makerspace/{id}/email/test`); it sends one message to your own account address. Until it is accepted the space sends through the platform account (if the Space Manager allows it). Editing any SMTP setting (host, port, login, password, TLS, From) means the account must pass the test again. Spaces that already used their own SMTP before this release were marked as passed for their current settings.

## Verify

- Save the settings, then trigger any email notification (for example a test booking confirmation) and watch **Email logs**.
- If delivery fails, the log row shows the error. Failed rows can be re-queued with `python manage.py flush_email_outbox` on deployments with no background worker.

## See also

- [Notification channels, rooms and recipients](../notification-routing.md)
- [Set up Telegram alerts](telegram-alerts.md)
