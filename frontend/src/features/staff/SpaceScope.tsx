import { useContext, useMemo, type ReactNode } from "react";

import { useTenantBootstrap } from "../inventory/usePublicInventory";
import { StaffListContext } from "./StaffListContext";

/**
 * Open items A19/A20 (role completeness EB2/EB3): a drawer opened from a cross-space list (assigned
 * events, assigned booking resources, organized events) belongs to the event's own space, which is
 * often not the space selected in the console. The space's public bootstrap supplies its switches.
 */
export function useSpaceSwitches(makerspaceId: number, slug: string) {
  const parent = useContext(StaffListContext);
  const bootstrap = useTenantBootstrap(slug, Boolean(slug));
  const same = parent.makerspace?.id === makerspaceId;
  const modules = bootstrap.data?.modules ?? (same ? parent.makerspace?.enabled_modules : undefined) ?? [];
  const features = bootstrap.data?.features ?? (same ? parent.makerspace?.enabled_features : undefined) ?? [];
  return { modules, features, loading: bootstrap.isLoading };
}

/**
 * Re-scopes the staff list context to the drawer's space so its panels (related activity, linked
 * finance, cross links) render for that space. Actions held in the selected space never carry over to
 * another space; the server decides each section from the person's real authority there.
 */
export function SpaceScope({ makerspaceId, slug, children }: { makerspaceId: number; slug: string; children: ReactNode }) {
  const parent = useContext(StaffListContext);
  const { modules, features } = useSpaceSwitches(makerspaceId, slug);
  const same = parent.makerspace?.id === makerspaceId;
  const key = JSON.stringify([modules, features]);
  const value = useMemo(() => same && !slug ? parent : {
    ...parent, actions: same ? parent.actions : [],
    makerspace: { id: makerspaceId, enabled_modules: modules, enabled_features: features },
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [parent, same, slug, makerspaceId, key]);
  return <StaffListContext.Provider value={value}>{children}</StaffListContext.Provider>;
}
