import { useEffect } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import type { StaffAuthUser } from "../../lib/api";
import type { SessionContext } from "../../lib/api/sessionContext";
import type { Makerspace } from "./panels/shared";

/**
 * `/admin/<tab>?context=platform&space=<slug>` -- the links on a makerspace's /control/
 * page (owner decision #115) -- opens the superadmin's console on that space, then drops
 * the hint from the URL so a reload or a later switch is not pulled back to it. The platform
 * overview (#183A) links by numeric id (`for_space=<id>`); a slug match always wins first.
 */
export function useSuperadminSpaceHint({ context, user, makerspaces, selected, setSelected }: {
  context: SessionContext; user: StaffAuthUser | null; makerspaces?: Makerspace[];
  selected: number | null; setSelected: (id: number | null) => void;
}) {
  const location = useLocation();
  const navigate = useNavigate();
  const search = new URLSearchParams(location.search);
  // `for_space` is the collision-free name (the platform overview); `space` stays for older links.
  const hintKey = search.has("for_space") ? "for_space" : "space";
  const hint = context === "platform" ? search.get(hintKey) : null;
  const superadmin = Boolean(user && (user.is_superuser || user.role === "superadmin"));
  useEffect(() => {
    if (!hint || !superadmin || !makerspaces) return;
    const space = makerspaces.find(item => item.slug === hint) ?? makerspaces.find(item => String(item.id) === hint);
    if (space && space.id !== selected) setSelected(space.id);
    const query = new URLSearchParams(location.search);
    query.delete(hintKey);
    navigate({ search: query.toString() }, { replace: true });
  }, [hint, hintKey, location.search, makerspaces, navigate, selected, setSelected, superadmin]);
}
