import type { ReactNode } from "react";
import type { LucideIcon } from "lucide-react";
import type { Action, Identity } from "../ui";

export type ShellItem = { key: string; label: string; href: string; icon: LucideIcon;
  badge?: number; badgeLabel?: string; children?: ShellItem[]; onSelect?: () => void };
export type ShellSection = { key: string; label?: string; caption?: string; items: ShellItem[]; more?: ShellItem[] };
export type ShellWorkspace = { name: string; subtitle: string; avatar: Identity; menu?: Action[]; locked?: boolean };
export type ShellUser = { name: string; role?: string; menu: Action[]; /** Omitted for a signed-out visitor: no Sign out entry. */ onSignOut?: () => void };
export type AppShellProps = {
  variant: "staff" | "member"; workspace?: ShellWorkspace;
  search?: { label: string; shortcut: "mod+k"; onOpen: () => void };
  nav: ShellSection[]; activeKey: string; footerLinks?: Action[]; user: ShellUser;
  compactNav: "drawer" | "bottom-tabs"; status?: ReactNode; children: ReactNode;
};
export const focusRing = "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus";
