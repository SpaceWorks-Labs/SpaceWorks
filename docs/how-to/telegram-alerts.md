---
title: Send alerts to a Telegram group
group: How-to guides
order: 30
summary: Connect a Telegram bot, add group rooms and choose which alerts each room hears.
---

# Send alerts to a Telegram group

Telegram is an **outbound** channel: SpaceWorks posts staff alerts into a group, and members can connect their own Telegram for private messages. You cannot accept or reject requests from chat; decisions are made in the staff console.

## Before you start

- The **Telegram** add-on is on for the space (**Areas & add-ons**).
- You created a bot with Telegram's `@BotFather` and have its token.
- You are a Space Manager.

## Steps

1. Open **Settings > Communication > Communication channels** and find **Telegram**.
2. Enter the **Bot username** (without the `@`) and the **Bot token**, then save. The token is stored encrypted and never shown again.
3. Add the bot to each Telegram group that should receive alerts.
4. Open **Settings > Communication > Notifications**, find **Rooms** and press **Add a room**:
   - **Channel**: Telegram.
   - **Room name**: for example "Laser team".
   - **Telegram chat ID**: the group's chat ID.
5. Optionally narrow the room to certain machines, machine types or inventory categories. A room with nothing selected receives everything; selections add up ("all the 3D printers, plus the laser").
6. Choose which events are sent in the notification matrix on the same page. Turning the channel on never starts sending by itself.
7. Back in **Communication channels**, use **Send a test** and pick the room.

> **Tip** All Telegram rooms in a space share that space's one bot. Add the same bot to every group and paste each group's own chat ID.

## What the bot never does

Alerts carry no buttons, and any button press that reaches the webhook is ignored. Rooms receive only the **staff** wording; member-facing text goes to email and to the member's own connected account, never into a shared room.

## Troubleshooting

| Symptom | Likely cause |
| --- | --- |
| Test succeeds for nobody | The bot was not added to the group, or the chat ID is wrong |
| Nothing arrives for an event | That event is muted in the notification matrix, or the room is narrowed to other machines |
| The channel shows **Review needed** | A configuration imported from an older setup needs you to review and release its hold |

## See also

- [Notification channels, rooms and recipients](../notification-routing.md)
- [Notifications v2](../notification-contract.md)
