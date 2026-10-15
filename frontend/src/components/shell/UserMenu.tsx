import { ChevronDown } from "lucide-react";
import { ActionControl, Avatar } from "../ui";
import { ThemeToggle } from "../ThemeToggle";
import { Disclosure } from "./Disclosure";
import type { ShellUser } from "./types";

export function UserMenu({ user, above = true, compact = false }: { user: ShellUser; above?: boolean; compact?: boolean }) {
  return <Disclosure above={above} label={<><span aria-hidden="true"><Avatar name={user.name} size="sm" /></span>
    <span className={compact ? "sr-only" : "min-w-0 flex-1"}><span className="block truncate text-sm font-semibold">{user.name}</span>{" "}
      {user.role ? <span className="block truncate text-xs text-muted">{user.role}</span> : null}</span>{compact ? null : <ChevronDown aria-hidden="true" size={24} />}</>}>
    {user.menu.map(action => <ActionControl key={action.label} action={action} className="w-full justify-start" />)}
    <div className="py-2"><ThemeToggle /></div>
    {user.onSignOut ? <button type="button" className="desk-button-ghost w-full justify-start" onClick={user.onSignOut}>Sign out</button> : null}
  </Disclosure>;
}
