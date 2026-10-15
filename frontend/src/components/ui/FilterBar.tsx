import type { ReactNode } from "react";
import { useId } from "react";
import { Search } from "lucide-react";

export type FilterBarProps = {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  searchLabel?: string;
  children?: ReactNode;
  actions?: ReactNode;
};

export function FilterBar({
  value,
  onChange,
  placeholder = "Search",
  searchLabel = "Search table",
  children,
  actions,
}: FilterBarProps) {
  const searchId = useId();

  return (
    <div className="flex min-w-0 flex-wrap items-center gap-3">
      <div className="relative min-w-0 flex-1 basis-full sm:basis-48">
      <label className="sr-only" htmlFor={searchId}>
        {searchLabel}
      </label>
      <input
        id={searchId}
        className="desk-input h-11 w-full min-w-0 border-outline bg-success pl-11 text-on-success placeholder:text-on-success dark:bg-surface dark:text-ink dark:placeholder:text-muted"
        type="search"
        value={value}
        placeholder={placeholder}
        onChange={(event) => onChange(event.target.value)}
      />
      <Search aria-hidden="true" className="pointer-events-none absolute left-3 top-1/2 size-5 -translate-y-1/2 text-on-success dark:text-muted" />
      </div>
      {children ? <div className="flex flex-wrap items-center gap-2">{children}</div> : null}
      {actions ? <div className="flex flex-wrap items-center gap-2 sm:ml-auto">{actions}</div> : null}
    </div>
  );
}
