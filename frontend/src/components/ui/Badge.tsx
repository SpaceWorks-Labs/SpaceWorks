import { t } from "@lingui/core/macro";
import type { PropsWithChildren } from "react";
import { StatusPill } from "./StatusPill";
import type { Tone } from "./types";
export type BadgeProps = PropsWithChildren<{ tone: Tone }>;
export function Badge({ tone, children }: BadgeProps) {
  return <StatusPill tone={tone} label={typeof children === "string" || typeof children === "number" ? String(children) : t`Status`}>{children}</StatusPill>;
}
