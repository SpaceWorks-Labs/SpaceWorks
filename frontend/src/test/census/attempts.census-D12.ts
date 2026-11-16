import { AsyncLocalStorage } from "node:async_hooks";

// Carry the actual browser gesture through awaited query/command transports. A concurrent poll cannot
// satisfy a Retry click, even when it targets the same screen-owned endpoint.
const attempts = new AsyncLocalStorage<string>();
export const requestAttempt = () => attempts.getStore();
export function runRetryAttempt<T>(control: string, activate: () => T): T {
  return attempts.run(control, activate);
}
