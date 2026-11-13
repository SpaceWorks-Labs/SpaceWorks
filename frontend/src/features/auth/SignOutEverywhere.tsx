import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { staffRequest } from "../../lib/api";
import { currentSessionContext } from "../../lib/api/sessionContext";
import { clearAccountSessions } from "../../lib/api/sessionTokens";
import { listQueues, wipeQueue } from "../kiosk/offlineQueueStore";
import { BoxArt } from "../../components/BoxSpinner";

export function SignOutEverywhere({ signInHref, onSignedOut }: { signInHref: string; onSignedOut?: () => void }) {
  const navigate = useNavigate();
  const client = useQueryClient();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const signOut = async () => {
    setPending(true); setError("");
    const context = currentSessionContext();
    try {
      await staffRequest("/auth/logout-all", { method: "POST", credentials: "include" }, context);
      const owner = await clearAccountSessions(context);
      // Also clear providers supplied outside SessionBoundary (including embeds).
      client.clear();
      // Station leases belong to their operator account, independently of cookies.
      await listQueues().then(queues => Promise.all(queues.filter(queue => owner && String(queue.lease.actor_id) === owner)
        .map(queue => wipeQueue(queue.scope)))).catch(() => undefined);
      onSignedOut?.();
      // Drop stale section/return URLs and router state along with queued UI actions.
      void navigate(signInHref, { replace: true, state: null });
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : t`Couldn't sign out everywhere. Try again.`);
    } finally { setPending(false); }
  };
  return <section className="grid gap-3" aria-label={t`Sign out everywhere`}>
    <p className="text-sm text-muted">{t`End this account’s sessions on every browser and device.`}</p>
    <button type="button" className="desk-button" disabled={pending} onClick={() => void signOut()}>
      {pending ? <><BoxArt size={16} mono />{t`Signing out…`}</> : t`Sign out everywhere`}
    </button>
    {error ? <p role="alert" className="text-sm text-danger">{error}</p> : null}
  </section>;
}
