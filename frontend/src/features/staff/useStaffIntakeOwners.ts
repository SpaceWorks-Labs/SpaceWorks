import { t } from "@lingui/core/macro";
import { useContext, useEffect, useRef } from "react";
import { onSessionCleared } from "../../lib/api/sessionContext";
import { getSessionOwner } from "../../lib/api/sessionTokens";
import { PendingIntake, type StaffBody } from "../inventory/contextualIntake";
import { useIntakeScope } from "../inventory/useIntakeScope";
import { StaffListContext } from "./StaffListContext";

/** Keep uncertain requests across list-page changes, never across actor or tenant changes. */
export function useStaffIntakeOwners(tenant: number) {
  const actor = useContext(StaffListContext).actorId;
  const session = useIntakeScope();
  const scope = JSON.stringify([session.context, session.owner, actor ?? null, tenant]);
  const store = useRef({ scope, owners: new Map<string, PendingIntake<StaffBody>>(), retired: false });
  if (store.current.scope !== scope) store.current = { scope, owners: new Map(), retired: false };
  const scopedStore = store.current;
  useEffect(() => {
    scopedStore.retired = false;
    const retire = () => {
      if (scopedStore.retired) return;
      scopedStore.retired = true;
      for (const owner of scopedStore.owners.values()) owner.clear();
      scopedStore.owners.clear();
    };
    const unsubscribe = onSessionCleared(context => {
      if (context === session.context && getSessionOwner(context) !== session.owner) retire();
    });
    return () => { unsubscribe(); retire(); };
  }, [scopedStore, session.context, session.owner]);
  return (key: string) => {
    if (scopedStore.retired) throw new Error(t`This request session is no longer active.`);
    let owner = scopedStore.owners.get(key);
    if (!owner) { owner = new PendingIntake<StaffBody>(); scopedStore.owners.set(key, owner); }
    return owner;
  };
}
