import type { ReactNode } from "react";
import type { IconName } from "./icon";
export type { IconName } from "./icon";
export type Tone = "success" | "warn" | "danger" | "accent" | "emphasis" | "info" | "neutral";

// Shared slot contracts for the page layouts and primitives.
export type Action = { label: string; href?: string; onClick?: () => void; icon?: IconName;
  pending?: boolean; pendingLabel?: string; disabled?: boolean; disabledReason?: string; // required when disabled
  tone?: "default" | "danger"; external?: boolean; confirms?: boolean;              // confirms → label gets "…"
  /** When set, the shared controls ask this before running onClick (destructive or hard-to-undo actions). */
  confirm?: { title: string; message: string; confirmLabel?: string } };
export type SecondaryAction = Action | { label: string; menu: Action[] };
export type Tab = { key: string; label: string; href?: string; count?: number };              // gated tabs are omitted, never disabled
export type Stat = { label: string; value: number | string; of?: number; progress?: number;   // 0–1
  tone?: "neutral" | "attention" | "danger" | "success"; href?: string };               // tone colours the number only
export type CalloutProps = { size: "banner" | "panel" | "card" | "inline"; tone: "warn" | "danger" | "success";
  lead: string; body?: string; action?: Action };                                       // ≤1 per screen
export type Identity = { kind: "date"; date: string } | { kind: "image"; src: string } |
  { kind: "icon"; icon: IconName; tone: Tone } | { kind: "avatar"; name: string; seed: string } |
  { kind: "code"; code: string };
export type QueryState = { status: "loading" | "error" | "ready"; error?: string; onRetry?: () => void };
export type EmptyProps = { message: string; action?: Action };                                 // P17 dashed card
export type PageHeaderProps = { eyebrow?: string; title: string; subtitle?: string; meta?: ReactNode;
  primary?: Action; secondary?: SecondaryAction; overflow?: Action[]; headingLevel?: 1 | 2;
  stickyPrimaryOnMobile?: boolean };
