import { t } from "@lingui/core/macro";
import { Bell, Hash, Mail, MessageCircle, MessageSquare, Send, Smartphone, Webhook } from "lucide-react";
import type { CataloguePart } from "./types";

/** Notifications group: the inbox and every outbound channel. */
const channel = (icon: typeof Bell, value: string, what: string, integrations: string[]) => ({
  icon, value, what, roles: [t`Space managers`], integrations,
});

export const messaging = (): CataloguePart => ({
  notifications: { icon: Bell, value: t`The inbox, quiet hours and digests.`,
    what: t`In-app notices for staff and members with quiet hours, daily digests and member preferences. API clients that talk to your space are issued here.`,
    roles: [t`Staff`, t`Members`], integrations: [t`Signed API clients`, t`Web push`] },
  email: channel(Mail, t`Email from your own sender.`, t`Receipts, reminders, lifecycle mail and report schedules by email, from your own address or the platform's.`,
    [t`SMTP`, t`Platform email relay`]),
  telegram: channel(Send, t`Alerts to a Telegram group.`, t`Outbound alerts for new requests and events. Decisions are made in the console, never in chat.`,
    [t`Telegram bot`]),
  slack: channel(Hash, t`Alerts to a Slack channel.`, t`Post request and event alerts to the channel your team already reads.`, [t`Slack incoming webhook`]),
  mattermost: channel(MessageSquare, t`Alerts to Mattermost.`, t`The same alerts for teams that run Mattermost.`, [t`Mattermost incoming webhook`]),
  discord: channel(MessageCircle, t`Alerts to Discord.`, t`The same alerts for communities that live on Discord.`, [t`Discord webhook`]),
  sms: channel(Smartphone, t`Text messages for what is urgent.`, t`SMS for reminders and codes when a provider is connected.`, [t`SMS provider`]),
  whatsapp: channel(MessageCircle, t`WhatsApp messages.`, t`Template messages over WhatsApp when connected.`, [t`WhatsApp Business`]),
  webhook: channel(Webhook, t`Signed webhooks to your own systems.`, t`Send events to your own tools with a signature your code can verify.`,
    [t`HMAC-signed HTTPS endpoints`]),
});
