---
title: Personal API tokens and connected apps
summary: Give a tool limited access to your account and revoke it when you finish.
order: 95
keywords: personal token, api access, connected app, oauth, revoke, disconnect
---
Open your account menu and choose **API access & connected apps**.

## Create a token

1. Under **New personal access token**, give the token a recognizable name.
2. Choose the permissions the tool needs. Staff permissions apply to the selected space.
3. Confirm your identity when asked.
4. Copy the token when it is displayed and keep it in your tool's secret store.

Return to **API access** to revoke a token when you finish using it. Revocation stops requests using it.

## Review an app connection

Check the app's name, destination and requested permissions before approving. Its requests follow your current permissions in each space. Disconnect it from **API access** when it no longer needs access.

> **Who can do this:** anyone with an active personal account. A permission on a token or app cannot give your account a new role.

![Screenshot: personal API token and connected-app controls, with secret values hidden](screenshot:member-api-access-and-apps)
