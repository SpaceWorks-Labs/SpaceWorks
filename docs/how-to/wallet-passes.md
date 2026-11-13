---
title: Add Apple Wallet and Google Wallet passes
group: How-to guides
order: 130
summary: Switch on wallet passes, add signing credentials for a space or the whole server, and test them.
---

# Add Apple Wallet and Google Wallet passes

Wallet passes put a member, programme or event card (and a guest pass) into the holder's Apple Wallet or Google Wallet. With the switch off, or with no complete credentials, no wallet button is shown anywhere.

## Before you start

- **Membership** is on and the `membership.wallet_passes` switch is on (**Settings > Areas > Features**). For event ID cards the switch is `events.wallet_passes`.
- Apple: a paid Apple Developer Program membership.
- Google: a Google Wallet Business issuer account and a Google Cloud project.
- Your API is reachable from phones over HTTPS (`PUBLIC_API_BASE_URL`), or passes will not refresh.

## Whose credentials sign the pass

Apple and Google are resolved separately. The first complete set wins:

1. the **space's own** credentials (**Settings > People > Membership > Wallet passes**, Space Manager);
2. the **platform's** credentials (**Platform settings > Integrations > Wallet passes**, superadmin);
3. deployment files named by the `WALLET_*` settings in the server environment.

## Apple

1. In developer.apple.com, create a **Pass Type ID** (for example `pass.org.yourspace.card`) and note your ten-character **Team ID**.
2. Create a certificate for it from a certificate signing request, then export a `.p12` with a password (or keep the certificate and private key as PEM).
3. Download **Apple WWDR G4** and convert it to PEM.
4. In SpaceWorks paste or upload the Pass Type ID, Team ID, the `.p12` and its password (or certificate plus key PEMs) and the WWDR PEM.

SpaceWorks checks the upload before saving: the key must match the certificate, the certificate must not be expired, and the Pass Type ID and Team ID must match the certificate. A mismatch fails with a field message instead of a silent "invalid pass" on a phone. Certificates last about a year; the page warns 30 days before expiry.

## Google

1. In the Google Wallet Business console create an **issuer** and copy the **Issuer ID**.
2. In Google Cloud enable the **Google Wallet API**, create a **service account** and a **JSON key**.
3. In the Wallet console add the service account's email as a user of the issuer with permission to manage passes.
4. In SpaceWorks paste the Issuer ID and the whole service-account JSON. Until Google approves your issuer for production, only test users listed in the console can save passes.

## Test

Open a member card on an iPhone and tap **Add to Apple Wallet**; on Android tap **Save to Google Wallet** with a test user. To check the signing logic without any account, run the offline verifier from a checkout:

```bash
python scripts/dev/verify_wallet_offline.py
```

## Troubleshooting

| Symptom | Likely cause |
| --- | --- |
| "The Pass Type ID does not match the certificate" | Copy the identifier exactly from Apple |
| Apple will not add the pass | Wrong or expired WWDR (use G4), expired certificate, or the Pass Type ID changed after issuing |
| Google save fails | Service account not added to the issuer, API not enabled, or issuer still in demo mode |
| No button at all | Switch off, credentials incomplete, or (guest passes) payment not cleared |

> **Warning** Changing the Apple Pass Type ID makes passes already in wallets unverifiable. The save response carries `reissue_needed: true`; ask holders to re-add their passes from **My passes**. Renewing a certificate for the same Pass Type ID does not need this.

Saved credentials are encrypted, write-only and never exported or moved with a space. Revoked holders' cards are voided (Apple) or set inactive (Google) on the next update, and their QR stops working at once.

## See also

- [Wallet passes reference](../wallet-passes.md)
