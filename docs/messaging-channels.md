# SMS and WhatsApp notifications

SMS and WhatsApp are addressed channels. Enable the relevant module, configure its
sender, enable the desired notification matrix cells, and ask each recipient to verify
their phone and consent in account settings. Both channels default off. Delivery
requires a tie to the makerspace: a non-revoked membership or an owned hardware
request/direct loan, booking, event registration, machine-service request or payment.
Account-only borrowers and other owners can opt in through Account → Messaging.
Inactive, restricted, suspended, deletion-pending accounts and global superadmins are
excluded from this member audience. A revoked membership disqualifies even an owner of
old rows. Ties are checked again at delivery; membership notification opt-out, personal
preferences, consent withdrawal and STOP suppression still prevent delivery. Staff
recipients retain their existing membership and role requirements.

Own credentials take precedence. An incomplete or broken own sender does not fall
back to the platform. Platform notifications also require the operator's channel switch
and the tenant's `use_platform_sender`. Shared platform senders share STOP protection
and WhatsApp correlation across all tenants.

## Where to configure

- Staff console → Settings → Email & integrations → SMS & WhatsApp: Space Managers
  configure their own credentials, clear stored secrets, allow platform fallback,
  inspect effective sender sources, copy the exact callback URLs/Meta verify token,
  and send a test to their own verified, consented phone. The relevant channel module
  must be enabled. Credential changes use the existing recent-reauthentication prompt.
- In the same section, WhatsApp template bindings select approved Meta template names,
  reviewed feature/event/audience combinations, supported languages and ordered BODY
  variables. Review and save imported bindings or bindings from a previous WABA before
  reactivating them. Platform bindings remain operator-managed in `/control/`.
- Staff console → Settings → Notifications → Notification channels: enable SMS/WhatsApp
  for each desired feature. Missing effective senders produce a setup warning.
- Member area for each makerspace → Account → Messaging: members inspect availability,
  their masked number and STOP status, and grant or withdraw each channel's consent.
  Account → Verify phone uses the existing phone-link verification flow. Opt-in requires
  verification; opt-out stays available without it. These account sections do not require
  the `notifications` module or its personal-preferences feature.

Test outcomes distinguish queued messages from skipped/suppressed messages. Queued does
not confirm provider delivery; the chosen event must also pass feature/matrix gates.

## Deployment configuration

Set `MESSAGING_WEBHOOK_BASE_URL` to the externally reachable callback origin, for
example `https://api.example.org`. A reverse-proxy deployment prefix is permitted.
The base excludes `/api/v1`, query strings and fragments. Keep its scheme, hostname,
path prefix and public port exact: Twilio verification uses that configured URL,
including the received query string, and ignores forwarded host headers.

Set `WHATSAPP_GRAPH_VERSION` to the deployed, supported Meta Graph version, using
`v<number>.<number>` syntax. The application default is `v23.0`. Provider secrets are
encrypted with `API_CLIENT_ENC_KEY`; keep that deployment key available when rotating
credentials. Do not place provider tokens in callback URLs or logs.

Workers discover `integrations.tasks_messaging`. Both Celery beat and
`python manage.py run_scheduled_tasks --due-only` run `messaging-recovery` every five
minutes. On brokerless deployments the latter is required; trigger it from the host's
scheduler. The credential wipe also has its own daily schedule.

## Twilio SMS provisioning

1. Provision an SMS-capable notification number and complete any Twilio-required
   registration for its country and number type. Enter Account SID, Auth Token and
   the E.164 From number in tenant messaging settings, or enable platform notification
   SMS in `/control/`.
2. Keep OTP on its separate platform number. A tenant cannot use the OTP Account SID
   or OTP number. The platform notification number must differ from the OTP number.
   **Never put the notification and OTP numbers in the same Messaging Service**:
   provider STOP enforcement must not disable login and account recovery. SpaceWorks
   submits `From` as a number, never a Messaging Service SID.
3. Set the number's **A message comes in** handler to HTTP POST and the inbound URL
   below. Enable **Advanced Opt-Out** for the Messaging Service/number configuration
   so signed `OptOutType` reaches SpaceWorks. Without it, the complete keyword list
   and send error `21610` still enforce opt-out.
4. Use the exact connection-override fragments shown below. SpaceWorks supplies the
   status callback on every outbound notification. Twilio strips the fragment when
   signing the request. Callbacks accept form encoding only, not JSON.

For a platform sender:

```text
https://api.example.org/api/v1/integrations/messaging/twilio/platform/inbound#rc=5&rp=5xx,ct,rt
https://api.example.org/api/v1/integrations/messaging/twilio/platform/status#rc=5&rp=5xx,ct,rt
```

For an own sender, replace `platform` with `m/42`, where `42` is the makerspace ID.
Inbound success returns empty `<Response/>` TwiML. STOP, STOPALL, UNSUBSCRIBE, CANCEL,
END, QUIT, REVOKE and OPTOUT suppress the sender/phone. `OptOutType` takes precedence
over text. START/UNSTOP/YES never lift application suppression: the member must
re-consent in the app with their verified current phone.

The implementation follows the repeated-parameter and port handling in
[Twilio's official RequestValidator](https://github.com/twilio/twilio-python/blob/main/twilio/request_validator.py).

## Meta WhatsApp provisioning

1. Use **one Meta app per sender configuration**: one for the platform sender, and
   each tenant's own app for its own sender. Add WhatsApp, verify the business phone
   number and retain its Phone Number ID and WhatsApp Business Account ID (WABA).
2. Register the Cloud API number with `POST /{phone_number_id}/register`, including
   `messaging_product=whatsapp` and the number's two-step verification PIN. This is an
   operator action in Meta; saving SpaceWorks settings does not register the number.
3. Create a system-user token with `whatsapp_business_messaging`, plus
   `whatsapp_business_management` for template validation. Store the token, app secret,
   WABA and phone ID in the sender settings. Keep PINs and tokens out of audit notes.
4. Configure the app's callback URL and verify token shown in SpaceWorks settings,
   subscribe the WABA to the app (`/{WABA_ID}/subscribed_apps`), and subscribe the app
   to the **messages** webhook field. The endpoint handles Meta's GET challenge and
   verifies POSTs using `X-Hub-Signature-256` over the exact raw JSON body.

```text
https://api.example.org/api/v1/integrations/messaging/whatsapp/platform
https://api.example.org/api/v1/integrations/messaging/whatsapp/m/42
```

Create approved templates in Meta, then bind the reviewed event, audience, template
name and language in SpaceWorks. V1 supports only positional text BODY parameters;
media headers, buttons and named parameters are rejected. Platform sends use platform
bindings; own sends use tenant bindings for the current WABA. A WABA change disables
old bindings until reviewed. No free-form session messages are sent.

## Test sends, recovery and bounded probe exposure

The settings test action accepts channel and an optional reviewed staff feature/event
to choose the WhatsApp binding. It targets only the caller's own verified, consented
phone and requires an active local membership and settings authority. The chosen event must pass
its feature and notification-matrix gates, along with channel, account, consent,
suppression, template and quota gates. Settings authority authorizes the test recipient. SMS identifies itself
as a test. WhatsApp uses the chosen approved template. Tests are limited to five per
user per hour and spend one logical-message quota unit when eligible. Managed defaults
are 100 SMS and 100 WhatsApp messages per tenant per day; self-host bypasses those quotas.
SMS billing can charge multiple segments; estimates cap at three conservative segments.

Every new WhatsApp sender/phone pair may submit one probe before correlation is
confirmed by a verified status webhook. Other deliveries defer without spending an
attempt. A timeout after the request may have been written ends the probe as
`failed(ambiguous_timeout)` and is **never resubmitted**. Its echoed
`biz_opaque_callback_data` allows a late callback to correlate even when the send
response was lost. Explicit provider rejections can retry within the four-attempt budget.

Confirmation requires a BSUID mapped to the phone, or an explicit matching recipient
phone when the sender has no unmapped alias STOPs. A new unmapped alias STOP blocks
all correlations whose aliases remain unknown; in-app re-consent permits a fresh probe
for a blocked pair. Missing callbacks expire waiting deliveries after 72 hours as
`skipped(identity_unconfirmed)`. This bounds exposure from an initially unmatchable
BSUID STOP to **one submitted probe**, including across concurrent tenants sharing a
sender. Check callback configuration and provider delivery logs before investigating
identity-unconfirmed skips. SMS requires no correlation probe.

Ordinary correlated sends are at least once: an ambiguous timeout can produce a
duplicate provider send. Leases last 90 seconds; stale workers cannot overwrite a new
claim. The recovery sweep retries due pending rows and expired leases, terminates
exhausted budgets and fails pending/sending rows older than seven days. It does not
re-reserve quota.

Verified callbacks are inserted durably before processing. Database failures return
500 for provider retry. Early callbacks wait for their message ID to be saved. A frozen
tenant's status callbacks retry for up to 30 days before abandonment; STOP protection
always applies, even with a frozen tenant or an uninstalled channel. Module removal
does not delete shared sender suppression or alias/correlation protection.

Credential rotation keeps prior verification secrets for 14 days, then wipes them.
Delivery progress never decreases; delivered/read evidence wins over a failure in
either arrival order. Provider timestamps are stored only when provided, and Twilio
`NumSegments` remains separate from estimates. Derived failed deliveries remain for
365 days; other terminal outcomes remain for 90 days from creation. Processed and
abandoned webhook events expire 30 days after processing/abandonment. Message bodies
and plaintext recipient numbers never enter delivery or webhook history.
