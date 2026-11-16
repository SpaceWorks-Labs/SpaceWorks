import { t } from "@lingui/core/macro";
import { useMemo } from "react";
import type { ApiClientScopeOption } from "./apiClientsApi";

export function ApiClientScopePicker({
  options,
  selected,
  onChange,
  disabled = false,
}: {
  options: ApiClientScopeOption[];
  selected: readonly string[];
  onChange: (scopes: string[]) => void;
  disabled?: boolean;
}) {
  const checked = useMemo(() => new Set(selected), [selected]);
  const grouped = useMemo(() => {
    const groups = new Map<string, ApiClientScopeOption[]>();
    options.forEach((option) => {
      groups.set(option.group, [...(groups.get(option.group) ?? []), option]);
    });
    return groups;
  }, [options]);
  const toggle = (value: string, grantable: boolean) => {
    if (disabled || !grantable) return;
    const next = new Set(checked);
    if (next.has(value)) next.delete(value); else next.add(value);
    onChange(options.filter((option) => next.has(option.value)).map((option) => option.value));
  };
  return (
    <div className="@container grid gap-2" aria-label={t`API client scopes`}>
      {Array.from(grouped.entries()).map(([group, groupOptions]) => (
        <section key={group} className="grid gap-3 @lg:grid-cols-2">
          <h4 className="title-section @lg:col-span-2">{group}</h4>
          {groupOptions.map((option) => (
            <label key={option.value} className="flex min-h-20 cursor-pointer items-start gap-3 rounded-xl border border-line bg-panel p-4 has-[:checked]:border-accent has-[:checked]:bg-accent-soft">
              <input
                className="mt-1 h-5 w-5 accent-accent focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
                type="checkbox"
                checked={checked.has(option.value)}
                disabled={disabled || !option.grantable}
                onChange={() => toggle(option.value, option.grantable)}
              />
              <span className="grid min-w-0 gap-0.5">
                <span className="font-semibold text-ink">{option.label}</span>
                <span className="text-xs text-muted">{option.description}</span>
                <span className="text-xs tabular-nums text-muted [overflow-wrap:anywhere]">{option.value}</span>
                {!option.grantable ? (
                  <span className="text-xs text-danger">
                    {option.lock_reason ?? t`This scope cannot be granted here.`}
                  </span>
                ) : null}
              </span>
            </label>
          ))}
        </section>
      ))}
    </div>
  );
}
