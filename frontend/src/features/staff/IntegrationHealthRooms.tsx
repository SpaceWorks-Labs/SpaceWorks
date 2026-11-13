import { t } from "@lingui/core/macro";
import { StatusPill as Badge } from "../../components/ui";
import { channelLabel } from "../notifications/channelCatalog";

// The backend has reported per-room delivery health since the destinations work
// (`integrations/health.py` -> `chat_destinations`); the console never rendered it, so the
// one surface where an operator could learn a room's webhook was revoked was invisible.

type LastFailure = { error: string; at: string } | null;

export type ChatRoomHealth = {
  id: number;
  channel: string;
  label: string;
  is_active: boolean;
  configured: boolean;
  last_sent_at: string | null;
  failed: number;
  last_failure: LastFailure;
};

export type LegacyChannelHealth = {
  configured: boolean;
  last_sent_at: string | null;
  failed: number;
  last_failure: LastFailure;
};

export type ChatDestinationsHealth = {
  status?: "ok" | "warn" | "error" | "unknown";
  detail?: string;
  destinations?: ChatRoomHealth[];
  legacy_deliveries?: Record<string, LegacyChannelHealth>;
};

export function IntegrationHealthRooms({
  section,
  formatTime,
}: {
  section?: ChatDestinationsHealth;
  formatTime: (value: string) => string;
}) {
  const rooms = section?.destinations ?? [];
  const legacy = Object.entries(section?.legacy_deliveries ?? {});
  if (!rooms.length && !legacy.length) {
    return <p className="text-sm text-muted">{t`No chat or webhook rooms are configured.`}</p>;
  }
  return (
    <ul className="grid gap-2 @lg:grid-cols-2">
      {rooms.map((room) => (
        <RoomRow
          key={`room-${room.id}`}
          title={`${channelLabel(room.channel)} - ${room.label}`}
          configured={room.configured}
          inactive={!room.is_active}
          health={room}
          formatTime={formatTime}
        />
      ))}
      {legacy.map(([channel, health]) => (
        <RoomRow
          key={`legacy-${channel}`}
          title={t`${channelLabel(channel)} (space-wide)`}
          configured={health.configured}
          inactive={false}
          health={health}
          formatTime={formatTime}
        />
      ))}
    </ul>
  );
}

function RoomRow({
  title,
  configured,
  inactive,
  health,
  formatTime,
}: {
  title: string;
  configured: boolean;
  inactive: boolean;
  health: LegacyChannelHealth;
  formatTime: (value: string) => string;
}) {
  return (
    <li className="min-w-0 rounded-md border border-line bg-surface p-3 text-sm">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="min-w-0 break-words font-semibold text-ink">{title}</p>
        {!configured ? (
          <Badge label="" tone="neutral">{t`Not configured`}</Badge>
        ) : inactive ? (
          <Badge label="" tone="neutral">{t`Inactive`}</Badge>
        ) : health.failed > 0 ? (
          <Badge label="" tone="danger">{`${health.failed} failed`}</Badge>
        ) : (
          <Badge label="" tone="success">{t`Healthy`}</Badge>
        )}
      </div>
      <p className="mt-1 text-xs text-muted">
        {health.last_sent_at ? t`Last sent ${formatTime(health.last_sent_at)}` : t`Never sent`}
      </p>
      {health.last_failure ? (
        <p className="mt-2 break-words text-danger">
          {t`Last delivery failed ${formatTime(health.last_failure.at)}: ${health.last_failure.error || "no detail"}`}
        </p>
      ) : null}
    </li>
  );
}
