import { lazy, type ReactNode } from "react";
import { Navigate } from "react-router-dom";
import { RouteFallback } from "../public/FamilyHome";
import { usePublicMakerspaces } from "../inventory/usePublicInventory";
import { useLandingEnabled } from "./useLandingEnabled";

const SpacesPage = lazy(() => import("../discover/spaces/SpacesPage").then(m => ({ default: m.SpacesPage })));

/** Decisions 300 and 424: wait for both answers before choosing the homepage. */
export function LandingGate({ landing }: { landing: ReactNode }) {
  const config = useLandingEnabled();
  const spaces = usePublicMakerspaces();
  if (config.loading || spaces.isLoading) return <RouteFallback />;
  if (config.enabled && (spaces.isError || !spaces.data?.length)) return <>{landing}</>;
  if (spaces.data?.length === 1) return <Navigate replace to={`/m/${encodeURIComponent(spaces.data[0].slug)}`} />;
  return <SpacesPage />;
}

/** The product landing remains reachable independently of the number of spaces. */
export function AboutLandingGate({ landing }: { landing: ReactNode }) {
  const config = useLandingEnabled();
  if (config.loading) return <RouteFallback />;
  return config.enabled ? <>{landing}</> : <Navigate replace to="/" />;
}
