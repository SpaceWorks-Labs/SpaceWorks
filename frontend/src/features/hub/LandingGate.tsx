import { lazy, type ReactNode } from "react";
import { Navigate } from "react-router-dom";
import { RouteFallback } from "../public/FamilyHome";
import { usePublicMakerspaces } from "../inventory/usePublicInventory";
import { useLandingEnabled } from "./useLandingEnabled";

const SpacesPage = lazy(() => import("../discover/spaces/SpacesPage").then((m) => ({ default: m.SpacesPage })));

/** Landing off: the only public space's home (same page as `/m/<slug>`), otherwise the directory. */
function FrontWithoutLanding() {
  const spaces = usePublicMakerspaces();
  if (spaces.isLoading) return <RouteFallback />;
  if (spaces.data?.length === 1) return <Navigate replace to={`/m/${encodeURIComponent(spaces.data[0].slug)}`} />;
  return <SpacesPage />;
}

/**
 * The central host's `/` (decision 300(b)). With the landing switched on it renders `landing`;
 * switched off, `FrontWithoutLanding`. Other routes never pass through here.
 */
export function LandingGate({ landing }: { landing: ReactNode }) {
  const config = useLandingEnabled();
  if (config.loading) return <RouteFallback />;
  return config.enabled ? <>{landing}</> : <FrontWithoutLanding />;
}
