---
title: Glossary
group: Getting started
order: 30
summary: The terms used across Space Works and its documentation.
---
# Glossary

| Term | Meaning |
| --- | --- |
| **Makerspace** | One tenant of the deployment. It owns its inventory, staff, public URL, QR namespace, chat rooms and audit scope. |
| **Organization** | A network, university or company that owns or reaches across makerspaces. Every new makerspace has an owner organization. |
| **Deployment** | One running installation of Space Works. It can host one space or many. |
| **Super Admin / superadmin** | The platform operator. Global across all spaces and always sees every space. Uses the `/control/` control plane. |
| **Role** | A bundle of actions. There are ten built-in roles per space. |
| **Action** | A single permission such as issuing a request. Authority comes from actions, not role names. |
| **Area manager** | A role that manages one area (inventory, machines, events, bookings, shop) and sees only that area's data. |
| **Handover** | The role and console used to issue and take back equipment at the front desk. |
| **Module** | An installable feature set with a registry key. Some are core and cannot be switched off. |
| **Feature / capability** | A switch inside a module, for example self-checkout or loan renewals. |
| **Request** | A borrow proposal. Staff acceptance reserves stock. |
| **Direct handout** | Staff issue equipment without a prior request. It still needs evidence. |
| **Self-checkout** | Eligible QR tools issued and returned by the borrower after authentication and photo evidence, where enabled. |
| **Reserve / issue / return** | The inventory movements, all counted by the availability module. |
| **Evidence** | The photo, QR scans and remark that prove a handover or return. |
| **Retention** | How long photo bytes are kept. The record of the photo is kept after the bytes expire. |
| **Audit log** | The append-only record of state changes. |
| **QR code** | A printed code that identifies a box or a tool unit. |
| **Box / container** | A physical container that holds items for a request. |
| **Kit** | A published set of items that can be requested together. |
| **Closed with issue** | A request ended because hardware was lost or damaged. It ties back to the borrower's access status. |
| **Access status** | Whether an account is active, restricted or suspended. |
| **Charge** | Money owed, recorded in the ledger whether or not online payments are on. |
| **Ledger** | The permanent record of payments, manual settlements, receipts and reconciliation. |
| **Rail** | The online payment path (checkout, refunds, Connect, webhooks). It is optional. |
| **Walk-in** | A person added at the counter with no account or password. |
| **Guest pass** | A dated permit for a non-member. |
| **API client** | A server system that signs requests to the public API. |
| **Personal access token** | A token a person creates to automate their own work. |
| **Publishable key** | A key that scopes a public website to one makerspace. |
| **Silo** | The bundled S3-compatible object store used in standard installs. |
| **Worker / beat** | The background job processes (Celery) and the scheduler that queues periodic work. |
