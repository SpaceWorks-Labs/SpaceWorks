export type EdgeEnvironment = Record<string, string | undefined> & { PUBLIC_ORIGIN: string; BACKEND_ORIGIN: string };
export function handleRequest(request: Request, env: EdgeEnvironment, assets: (request: Request) => Promise<Response>,
  fetcher?: typeof fetch, clientIp?: string): Promise<Response>;
