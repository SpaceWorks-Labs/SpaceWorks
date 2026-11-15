import { fireEvent, screen, waitFor } from "@testing-library/react";
import { isDeepStrictEqual } from "node:util";
import type { RouteCase } from "./source.census-D12";
import type { Phase } from "./fetch.census-D12";
import { commandFromSource } from "./commands.census-D12";
import { effectFor, protocolFor, type BrowserCommand } from "./protocols.census-D12";

const QR = "3f9a1c2b4d5e6f7081920a1b2c3d4e5f";
const CONFIRMATION = "d12-enrollment-proof";
// Two protocol adapters: a fragment-bound proof and the shared ScanWorkbench.
// Generic response schemas cannot infer browser secrets or user gestures.
export function actionFor(row: RouteCase): BrowserCommand | undefined {
  if (row.screen === "ReauthenticationReturn" && row.pattern === "/reauth/confirm") return {
    path: "/auth/reauth/enrollment/confirm", body: { token: CONFIRMATION }, fragment: `#token=${CONFIRMATION}`,
    button: "Confirm enrollment", idle: "This link works once, in the same browser session that requested it.",
  };
  if (row.screen === "ScannerPage" || row.leaves?.includes("ScannerPanel")) return {
    path: "/admin/qr/resolve", body: row.screen === "ScannerPage" ? { payload: QR } : { payload: QR, makerspace_id: 1 },
    fragment: "", button: "Find", idle: "Scan a QR code or find an item to get started.",
  };
  return protocolFor(row) ?? commandFromSource(row);
}
export async function activateAction(row: RouteCase, phase: Phase) {
  // Native details content is intentionally hidden until a user opens it.
  // Open the disclosure, never submit or grant consent on the user's behalf.
  if (row.screen === "PhotoChoice") {
    const summary = await screen.findByText("Badge photo and public cards", { exact: true });
    const details = summary.closest("details")!;
    details.open = true;
    fireEvent(details, new Event("toggle", { bubbles: false }));
  }
  const action = actionFor(row);
  if (!action || phase === "empty") return;
  if (action.file) { await fillAction(row); return; }
  if (action.disclosure) {
    const summary = await screen.findByText(action.disclosure, { exact: true });
    const details = summary.closest("details")!;
    details.open = true; fireEvent(details, new Event("toggle"));
  }
  const button = await screen.findByRole("button", { name: action.button });
  await fillAction(row);
  // Account restoration can render the command before its authority-bearing
  // prerequisites finish. A click on that disabled native control does nothing.
  await waitFor(() => {
    if (button.hasAttribute("disabled")) throw new Error(`D12 action is not enabled: ${action.button}`);
  }, { timeout: 5000 });
  fireEvent.click(button);
}
export async function fillAction(row: RouteCase) {
  const action = actionFor(row);
  if (!action) return;
  if (action.file) fireEvent.change(await screen.findByLabelText(action.file.label), {
    target: { files: [new File(["d12"], action.file.name, { type: "image/png" })] },
  });
  if (action.path === "/admin/qr/resolve") {
    const input = await screen.findByRole("searchbox", { name: "QR payload" });
    fireEvent.change(input, { target: { value: QR } });
  }
  for (const input of action.inputs ?? []) fireEvent.change(await screen.findByLabelText(input.label, { exact: true }),
    { target: { value: input.value } });
  for (const label of action.checks ?? []) {
    const input = await screen.findByRole("checkbox", { name: label });
    if (!(input as HTMLInputElement).checked) fireEvent.click(input);
  }
}
export function checkActionRequest(row: RouteCase | undefined, method: string, path: string, body: unknown, headers?: HeadersInit) {
  const effect = row && effectFor(row);
  if (effect && method === "POST" && path === effect.path) {
    if (JSON.stringify(body) !== JSON.stringify(effect.body)) throw new Error(`D12 effect proof does not match ${row!.screen}`);
    return;
  }
  // This screen consumes a path-bound invitation automatically after restoring
  // the account; no simulated click can precede that effect.
  if (row?.screen === "OrganizationInvitationRedeemPage" && method === "POST"
    && path === "/auth/organization-invitations/redeem") {
    if (JSON.stringify(body) !== JSON.stringify({ token: row.path.split("/").pop() }))
      throw new Error("D12 organization invitation token does not match the routed token");
    return;
  }
  const action = row && actionFor(row);
  if (!action || method !== "POST" || path !== action.path)
    throw new Error(`D12 unplanned mutation ${method} ${path}`);
  const operation = action.operation && body && typeof body === "object" ? (body as Record<string, unknown>).operation_id : undefined;
  if (action.operation && (typeof operation !== "string" || !/^[a-f0-9]{8}-(?:[a-f0-9]{4}-){3}[a-f0-9]{12}$/i.test(operation)
    || new Headers(headers).get("Idempotency-Key") !== operation)) throw new Error("D12 command requires matching operation UUID and idempotency header");
  const expected = action.operation ? { ...action.body as object, operation_id: operation } : action.body;
  if (!isDeepStrictEqual(body, expected))
    throw new Error(`D12 action payload does not match ${row!.screen}: ${method} ${path}`);
}
