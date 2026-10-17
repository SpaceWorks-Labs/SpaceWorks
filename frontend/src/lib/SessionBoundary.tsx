import type { ReactNode } from "react";
import { QueryClientProvider } from "@tanstack/react-query";
import { useLocation } from "react-router-dom";
import { useTenant } from "./tenant";
import { contextForRoute, setRouteSessionContext } from "./api/sessionContext";
import { queryClientForContext } from "./queryClient";

/** A separate cache also isolates identical query keys and pending mutations. */
export function SessionBoundary({ children }: { children: ReactNode }) {
  const { pathname, search } = useLocation();
  const tenant = useTenant();
  const context = contextForRoute(pathname, search, tenant.slug);
  setRouteSessionContext(context);
  return <QueryClientProvider key={context} client={queryClientForContext(context)}>{children}</QueryClientProvider>;
}
