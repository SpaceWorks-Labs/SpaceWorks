import { act, fireEvent, screen, waitFor } from "@testing-library/react";
import { expect } from "vitest";
import type { RouteCase } from "./source.census-D12";
import { REFUSALS, type Exchange } from "./fetch.census-D12";
import { actionFor, fillAction } from "./actions.census-D12";
import { retryControls } from "./refusals.census-D12";
import { runRetryAttempt } from "./attempts.census-D12";

export const operationKey = (exchange: Exchange) => `${exchange.operation ?? "local"} ${exchange.method} ${exchange.target}`;
const own = (exchanges: Exchange[]) => exchanges.filter(exchange => !exchange.support && !exchange.outside);

/** Pin the failed operation set before any gesture. Support/provider traffic cannot create obligations or satisfy them. */
export function retryProof(exchanges: Exchange[]) {
  const failed = new Map(own(exchanges).filter(exchange => exchange.status === REFUSALS.error.status)
    .map(exchange => [operationKey(exchange), exchange]));
  expect(failed.size, "No failed screen-owned operation to retry").toBeGreaterThan(0);
  const bindings = new Map<string, Set<string>>();
  return {
    attempt(control: string, fresh: Exchange[], gesture = control) {
      const attempts = own(fresh).filter(exchange => control === "automatic poll" || exchange.attempt === gesture);
      expect(attempts.length, `No new screen-owned attempt for ${control}`).toBeGreaterThan(0);
      const operations = new Set<string>();
      for (const exchange of attempts) {
        const key = operationKey(exchange);
        expect(failed.has(key), `${control} retried an unrelated operation: ${key}`).toBe(true);
        const original = failed.get(key)!;
        expect({ method: exchange.method, target: exchange.target, operation: exchange.operation })
          .toEqual({ method: original.method, target: original.target, operation: original.operation });
        expect({ status: exchange.status, code: (exchange.body as { code?: string } | null)?.code })
          .toEqual({ status: 503, code: "service_unavailable" });
        operations.add(key);
      }
      // A second activation must retry the same operation(s) as the first activation of this control.
      const previous = bindings.get(control);
      if (previous) expect([...operations].sort(), `Retry binding changed: ${control}`).toEqual([...previous].sort());
      else bindings.set(control, operations);
    },
    complete() {
      const covered = new Set([...bindings.values()].flatMap(keys => [...keys]));
      const missing = [...failed.keys()].filter(key => !covered.has(key));
      expect(missing, `Failed operations without their own retry proof: ${missing.join(" ; ")}`).toEqual([]);
    },
  };
}

export async function assertScreenRetries(row: RouteCase, network: { exchanges: Exchange[] },
  settled: () => Promise<void>, autoMs?: number) {
  // Cache settlement precedes React Query's scheduled observer notification. Commit it before taking the control snapshot.
  await settled();
  await act(async () => { await new Promise(resolve => setTimeout(resolve, 0)); });
  const proof = retryProof(network.exchanges);
  let serial = 0;
  const attempt = async (name: string, activate: () => void | Promise<void>, timeout = 5000) => {
    const before = network.exchanges.length;
    const gesture = `${row.id}: ${name}: ${++serial}`;
    await runRetryAttempt(gesture, activate);
    await waitFor(() => expect(own(network.exchanges.slice(before)).some(exchange =>
      name === "automatic poll" || exchange.attempt === gesture), `No new screen-owned attempt for ${name}`).toBe(true), { timeout });
    await settled();
    proof.attempt(name, network.exchanges.slice(before), gesture);
  };
  if (autoMs) {
    await attempt("automatic poll", () => undefined, autoMs + 3000);
  } else {
    const action = actionFor(row);
    if (action?.file) {
      const control = screen.getByLabelText(action.file.label);
      expect(control.tagName).toBe("INPUT"); expect(control).toHaveAttribute("type", "file");
      expect(control).toBeEnabled(); control.focus(); expect(document.activeElement).toBe(control);
      await attempt(action.file.label, async () => {
        expect(fireEvent.keyDown(control, { key: "Enter", code: "Enter" })).toBe(true);
        await fillAction(row);
      });
    } else {
      const choices = [...new Set(retryControls(row))];
      const usesAction = !choices.length && Boolean(action);
      if (usesAction && action) {
        await fillAction(row);
        choices.push(...screen.queryAllByRole("button", { name: action.button }));
      }
      expect(choices.length, `No retry control: ${row.id}`).toBeGreaterThan(0);
      for (const [index, initial] of choices.entries()) {
        expect(initial.tagName).toBe("BUTTON");
        const label = initial.textContent;
        const occurrence = choices.slice(0, index).filter(node => node.textContent === label).length;
        const activate = async () => {
          if (action) await fillAction(row);
          let control!: HTMLElement;
          await waitFor(() => {
            const current = usesAction && action ? screen.queryAllByRole("button", { name: action.button }) : retryControls(row);
            control = current.filter(node => node.textContent === label)[occurrence];
            expect(control).toBeInTheDocument(); expect(control).toBeEnabled();
          });
          control.focus(); expect(document.activeElement).toBe(control);
          expect(fireEvent.keyDown(control, { key: "Enter", code: "Enter" })).toBe(true);
          fireEvent.click(control); // jsdom does not synthesize Enter's native click.
          fireEvent.keyUp(control, { key: "Enter", code: "Enter" });
        };
        const name = `${index}: ${label}`;
        await attempt(name, activate);
        await attempt(name, activate);
      }
    }
  }
  proof.complete();
}
