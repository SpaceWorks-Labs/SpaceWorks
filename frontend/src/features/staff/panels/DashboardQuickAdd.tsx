import { t } from "@lingui/core/macro";
import { consoleSessionHref } from "../../../lib/api/sessionContext";
import { useState, type ReactNode } from "react";
import { ListRow, Modal, type Action } from "../../../components/ui";
import { quickCreateCommands } from "../quickCreate";
import { staffTabPath } from "../staffTabs";
import type { Makerspace } from "./shared";

export function DashboardQuickAdd({ makerspace, allowedTabs, actions, isSuperadmin, guestOnly, singleTenantLocked, children }: {
  makerspace: Makerspace; allowedTabs?: readonly string[]; actions?: readonly string[]; isSuperadmin: boolean;
  guestOnly: boolean; singleTenantLocked: boolean; children: (primary?: Action) => ReactNode;
}) {
  const [open, setOpen] = useState(false);
  const commands = allowedTabs && actions ? quickCreateCommands(actions, allowedTabs, isSuperadmin) : [];
  const choices = commands.map(command => ({ label: command.label,
    href: consoleSessionHref(`${staffTabPath(command.tab, guestOnly, makerspace.slug, singleTenantLocked)}?${new URLSearchParams(command.query)}`) }));
  const primary: Action | undefined = choices.length === 1 ? choices[0]
    : choices.length ? { label: t`Quick add`, icon: "Plus", onClick: () => setOpen(true) } : undefined;
  return <>{children(primary)}<Modal open={open} onClose={() => setOpen(false)} title={t`Quick add`}>
    <div className="grid gap-3">{choices.map(choice => <ListRow key={choice.href} title={choice.label} href={choice.href} />)}</div>
  </Modal></>;
}
