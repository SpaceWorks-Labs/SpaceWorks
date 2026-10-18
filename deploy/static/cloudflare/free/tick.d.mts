export function runScheduledTick(env: Record<string, string>, fetcher?: typeof fetch,
  sleep?: (ms: number) => Promise<void>): Promise<{ status: string }>;
