import { t } from "@lingui/core/macro";
/** Chat channels a room may post into. Ordered as the picker shows them. */
export const CHANNELS = [
  { key: "slack", label: t`Slack` },
  { key: "mattermost", label: t`Mattermost` },
  { key: "discord", label: t`Discord` },
  { key: "telegram", label: t`Telegram` },
  { key: "webhook", label: t`Signed webhook` },
] as const;

export const DESTINATIONS_KEY = (makerspaceId: number) =>
  ["notification-destinations", makerspaceId] as const;
