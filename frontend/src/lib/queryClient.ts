import { QueryClient } from "@tanstack/react-query";
import { onSessionCleared, type SessionContext } from "./api/sessionContext";

const createClient = () => new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

const clients = new Map<SessionContext, QueryClient>();
export function queryClientForContext(context: SessionContext) {
  if (!clients.has(context)) clients.set(context, createClient());
  return clients.get(context)!;
}
export const queryClient = queryClientForContext("person");
onSessionCleared(context => clients.get(context)?.clear());
