import { useRef, useState, useEffect } from "react";
import { Copy } from "lucide-react";
import { ErrorText, Field, Modal } from "../../../../components/ui";
import { setStaffPassword, type StaffAccount } from "../../../../lib/api/staffAccounts";

/** Secrets stay in this mounted dialog, outside Query/Mutation caches and storage. */
export function StaffPasswordDialog({ space, account, onClose, onSaved }: {
  space: number; account: StaffAccount; onClose: () => void; onSaved: () => void;
}) {
  const [generate, setGenerate] = useState(true);
  const [password, setPassword] = useState("");
  const [resetMfa, setResetMfa] = useState(false);
  const [pending, setPending] = useState(false);
  const [saved, setSaved] = useState(false);
  const [secret, setSecret] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState("");
  const mounted = useRef(true);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  const submit = async () => {
    if (pending || (!generate && !password)) return;
    setPending(true); setError("");
    try {
      const result = await setStaffPassword(space, account.id, { ...(generate ? { generate: true } : { password }), reset_mfa: resetMfa });
      if (!mounted.current) return;
      setPassword(""); setSecret(result.generated_password); setSaved(true); onSaved();
    } catch (failure) {
      if (mounted.current) setError(failure instanceof Error ? failure.message : "Unable to set password.");
    } finally { if (mounted.current) setPending(false); }
  };
  return <Modal open title={`Set password for ${account.display_name || account.username}`} onClose={() => { if (!pending) onClose(); }}>
    <div className="grid gap-4">
      {saved ? <>
        <p role="status" className="text-sm text-ink">Password set. Previous sessions have ended. They must change this password at next sign-in.</p>
        {secret ? <>
          <p className="text-sm text-muted">Shown once. Share privately before closing this dialog.</p>
          <Field label="Generated password"><input className="desk-input w-full code-text" readOnly value={secret} /></Field>
          <button className="desk-button inline-flex items-center justify-center gap-2" type="button" onClick={() => {
            void navigator.clipboard.writeText(secret).then(() => setCopied(true)).catch(() => setError("Copy failed. Select and copy the password manually."));
          }}><Copy size={16} aria-hidden />{copied ? "Copied" : "Copy password"}</button>
        </> : null}
        <button className="desk-button-primary" onClick={onClose}>Done</button>
      </> : <form className="grid gap-4" onSubmit={e => { e.preventDefault(); void submit(); }}>
        <label className="flex min-h-11 items-center gap-3"><input type="checkbox" checked={generate} disabled={pending} onChange={e => { setGenerate(e.target.checked); setPassword(""); }} />Generate a password</label>
        {!generate ? <Field label="New password"><input className="desk-input w-full" type="password" autoComplete="new-password" required disabled={pending} value={password} onChange={e => setPassword(e.target.value)} /></Field> : null}
        <label className="flex min-h-11 items-center gap-3"><input type="checkbox" checked={resetMfa} disabled={pending} onChange={e => setResetMfa(e.target.checked)} />Reset authenticator</label>
        <p className="text-sm text-muted">This ends existing sessions and requires a new password at next sign-in.</p>
        <button className="desk-button-primary" disabled={pending || (!generate && !password)}>{pending ? "Setting password…" : "Set password"}</button>
      </form>}
      {error ? <ErrorText message={error} /> : null}
    </div>
  </Modal>;
}
