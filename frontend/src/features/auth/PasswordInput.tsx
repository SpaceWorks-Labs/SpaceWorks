import { t } from "@lingui/core/macro";
import { useState, type ComponentProps } from "react";

/** One reveal control keeps password fields usable without changing their values. */
export function PasswordInput(props: Omit<ComponentProps<"input">, "type">) {
  const [visible, setVisible] = useState(false);
  return <div className="flex min-w-0 items-center gap-2">
    <input {...props} type={visible ? "text" : "password"} className={`desk-input min-w-0 flex-1 ${props.className ?? ""}`} />
    <button type="button" className="desk-button min-h-11 min-w-11" aria-label={visible ? t`Hide password` : t`Show password`}
      aria-pressed={visible} onClick={() => setVisible(!visible)}>{visible ? t`Hide` : t`Show`}</button>
  </div>;
}
