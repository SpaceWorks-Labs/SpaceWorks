---
title: API access and signed webhooks
summary: Connect other systems with API clients, and push events out through signed webhooks.
order: 100
keywords: api, api client, secret, scopes, integration, webhook, developer, origins
---
## Create an API client

1. Open **API access** and press **New API client**.
2. Give it a label, choose the **API scopes** it needs, and list any **Allowed browser origins**.
3. Press **Create API client**.
4. Copy the secret now; it's shown once. Press **Copy**, then **Done**.

![Screenshot: the New API client form](screenshot:sm-api-client)

On an existing client, use **Edit scopes**, **Rotate secret** or **Delete**. **Developer reference** shows your space's code for the developer.

Other staff see **Request API access** instead: they describe what they need, and you decide.

## Signed webhooks

1. Open **Settings**, then **Notifications**, and **Add a room**.
2. Set **Channel** to **Signed webhook** and enter the address.
3. Choose the **Payload format**. The newer structured format sends IDs only, never personal details.
4. Press **Save room**.

> **Who can do this:** the Space Manager creates clients and webhooks. Other staff (apart from front-desk-only staff) can request access.
