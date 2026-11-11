import { t } from "@lingui/core/macro";
import { Check, Copy } from "lucide-react";
import { useState } from "react";

/** A labelled, copyable shell snippet. The status line says whether the copy worked. */
export function ApiCopyBlock({ label, code }: { label: string; code: string }) {
  const [state, setState] = useState<"idle" | "copied" | "failed">("idle");
  const copy = () => {
    void Promise.resolve().then(() => navigator.clipboard.writeText(code))
      .then(() => setState("copied")).catch(() => setState("failed"));
  };
  return <figure className="overflow-hidden rounded-xl border border-line bg-surface">
    <figcaption className="flex items-center justify-between gap-3 border-b border-line px-3 py-1.5 text-xs font-semibold text-muted">
      <span>{label}</span>
      <button type="button" onClick={copy} className="inline-flex min-h-9 items-center gap-1.5 rounded-control px-2 text-xs font-semibold text-ink hover:bg-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus">
        {state === "copied" ? <Check size={16} aria-hidden="true" /> : <Copy size={16} aria-hidden="true" />}
        {state === "copied" ? t`Copied` : t`Copy`}
      </button>
    </figcaption>
    <pre className="overflow-x-auto p-3 text-sm leading-6 text-ink sm:p-4"><code className="code-text whitespace-pre">{code}</code></pre>
    <p role="status" className={state === "failed" ? "border-t border-line px-3 py-2 text-sm text-danger" : "sr-only"}>{state === "copied" ? t`Copied to the clipboard.` : state === "failed" ? t`Couldn't copy. Select the text to copy it.` : ""}</p>
  </figure>;
}
