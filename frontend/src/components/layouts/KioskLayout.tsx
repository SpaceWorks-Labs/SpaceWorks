import { t } from "@lingui/core/macro";
import type { ReactNode } from "react";
import { AnimatedLogoMark } from "../brand/AnimatedLogoMark";
import { ActionControl, Callout, Card, ConfirmDialog, PageHeader, StatusPill } from "../ui";
import type { Action, Identity } from "../ui";
import { KioskPin, type KioskPinProps } from "./KioskPin";
import { LayoutFrame, QueryContent } from "./LayoutFrame";
import type { LayoutProps } from "./types";

export type KioskLayoutProps = LayoutProps & {
  context: { identity?: Identity; title: string; subtitle: string };
  connection: { online: boolean; queued?: number };
  progress?: { done: number; of: number; label: string };
  headerActions: Action[];
  mode: "lock" | "ready" | "work";
  lock?: KioskPinProps;
  ready?: { primary: Action };
  work?: { capture: ReactNode; panel: ReactNode; recent?: ReactNode };
  idleCountdown?: { seconds: number; onKeep: () => void };
  confirmLock?: { pendingCount?: number; title?: string; consequence?: string; onDiscard: () => void; onKeep: () => void };
};
export function KioskLayout({ context, connection, progress, headerActions, mode, lock, ready, work, idleCountdown,
  confirmLock, standalone = true, width = "default", ...query }: KioskLayoutProps) {
  const connectionLabel = connection.queued
    ? (connection.online ? t`Online · ${connection.queued} queued` : t`Offline · ${connection.queued} queued`)
    : (connection.online ? t`Online` : t`Offline`);
  return <div className="sw-kiosk bg-bg text-ink">
    <LayoutFrame standalone={standalone} width={width}>
      <div className="mb-6 flex min-w-0 items-start gap-3">
        <AnimatedLogoMark variant="symbol" size={48} />
        <div className="min-w-0 flex-1 [&>header]:mb-0"><PageHeader title={context.title} subtitle={context.subtitle} identity={context.identity}
        meta={<div className="flex flex-wrap items-center gap-4">
          {progress ? <span className="font-display text-2xl tabular-nums">{`${progress.done} / ${progress.of} ${progress.label}`}</span> : null}
          <StatusPill label={connectionLabel} tone={connection.online ? "success" : "warn"} />
        </div>} /></div>
      </div>
      <div className="mb-8 flex flex-wrap justify-end gap-3">{headerActions.map(action => <ActionControl key={action.label} action={action} />)}</div>
      {idleCountdown ? <div className="mb-6"><Callout size="panel" tone="warn" lead={`Station locks in ${idleCountdown.seconds} seconds.`}
        action={{ label: t`Keep working`, onClick: idleCountdown.onKeep }} /></div> : null}
      <QueryContent {...query}>
        {mode === "lock" && lock ? <><KioskPin {...lock} />
          {work?.panel ? <div className="mt-6">{work.panel}</div> : null}</> : null}
        {mode === "ready" && ready ? <Card className="grid min-h-64 place-items-center"><ActionControl action={ready.primary} primary /></Card> : null}
        {mode === "work" && work ? <div className="grid gap-8"><div className="sw-kiosk-stage">
          <div className="min-w-0">{work.capture}</div><div className="min-w-0">{work.panel}</div>
        </div>{work.recent}</div> : null}
      </QueryContent>
    </LayoutFrame>
    <ConfirmDialog open={Boolean(confirmLock)} title={confirmLock?.title ?? t`Lock this station?`}
      message={confirmLock?.consequence ?? t`${confirmLock?.pendingCount ?? 0} queued actions are still on this device.`} confirmLabel={t`Discard and lock`} cancelLabel={t`Keep working`}
      tone="danger" safePrimary onConfirm={() => confirmLock?.onDiscard()} onCancel={() => confirmLock?.onKeep()} />
  </div>;
}
