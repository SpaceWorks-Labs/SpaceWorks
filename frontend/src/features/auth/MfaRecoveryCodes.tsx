import { useState } from "react";
import { ErrorBlock } from "../../components/ui";

/** The already-issued codes stay in memory; copying and downloading do not call the API. */
export function MfaRecoveryCodes({ codes }: { codes: string[] }) {
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const text = codes.join("\n");
  const copy = async () => {
    setError(null);
    try { await navigator.clipboard.writeText(text); setCopied(true); }
    catch { setError(new Error("Couldn't copy codes. Try again.")); }
  };
  const download = () => {
    setError(null);
    try {
      const url = URL.createObjectURL(new Blob([text], { type: "text/plain;charset=utf-8" }));
      const link = document.createElement("a");
      link.href = url; link.download = "space-works-recovery-codes.txt"; link.click();
      URL.revokeObjectURL(url);
    } catch { setError(new Error("Couldn't download codes. Try again.")); }
  };
  return <div className="grid gap-4">
    <ul aria-label="Recovery codes" className="grid grid-cols-2 gap-2 rounded-xl border border-line bg-surface p-4">
      {codes.map(code => <li className="code-text break-all text-sm tracking-wide" key={code}>{code}</li>)}
    </ul>
    <div className="flex flex-wrap gap-3"><button className="desk-button" type="button" onClick={() => { void copy(); }}>Copy all</button>
      <button className="desk-button" type="button" onClick={download}>Download .txt</button></div>
    {copied ? <p role="status" className="text-sm text-muted">Codes copied.</p> : null}
    {error ? <ErrorBlock error={error} /> : null}
  </div>;
}
