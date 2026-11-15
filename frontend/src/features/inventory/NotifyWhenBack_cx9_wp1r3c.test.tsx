import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, expect, it, vi } from "vitest";
import source from "./NotifyWhenBack.tsx?raw";
import { NotifyWhenBack } from "./NotifyWhenBack";

const { request } = vi.hoisted(() => ({ request: vi.fn() }));
vi.mock("../../lib/api", () => ({ tenantPublicRequest: request }));
const methods = [...source.matchAll(/method:\s*"(\w+)"/g)].map(match => match[1]);
beforeEach(() => request.mockReset());

it("covers every real watch transport method and no destination input", () => {
  expect([...methods].sort()).toEqual(["DELETE", "POST"]);
});

for (const method of methods) {
  for (const outcome of ["success", "refusal"] as const) {
    it(`${method} pending and ${outcome} preserve the correct subscription state`, async () => {
      const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
      request.mockResolvedValue({ subscribed: true });
      const view = render(<QueryClientProvider client={client}><NotifyWhenBack slug="lab" productId={7} /></QueryClientProvider>);
      if (method === "DELETE") {
        fireEvent.click(screen.getByRole("button", { name: "Notify me when back" }));
        await screen.findByRole("button", { name: "Cancel notification" });
      }
      request.mockClear();
      let resolve!: (value: unknown) => void;
      let reject!: (error: Error) => void;
      request.mockImplementationOnce(() => new Promise((yes, no) => { resolve = yes; reject = no; }));
      fireEvent.click(screen.getByRole("button", { name: method === "POST" ? "Notify me when back" : "Cancel notification" }));
      await waitFor(() => expect(screen.getByRole("button")).toBeDisabled());
      expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
      expect(request.mock.calls).toEqual([["lab", "/public/lab/inventory/7/watch/",
        method === "POST" ? { method: "POST", body: "{}" } : { method: "DELETE" }]]);
      await act(async () => {
        if (outcome === "refusal") reject(new Error("An active membership is required."));
        else resolve({ subscribed: true });
      });
      await waitFor(() => expect(screen.getByRole("button")).toBeEnabled());
      const subscribed = method === "POST" ? outcome === "success" : outcome === "refusal";
      expect(screen.getByRole("button", { name: subscribed ? "Cancel notification" : "Notify me when back" })).toBeInTheDocument();
      expect(screen.queryAllByRole("status")).toHaveLength(subscribed ? 1 : 0);
      if (outcome === "refusal") expect(screen.getByRole("alert")).toHaveTextContent("An active membership is required.");
      else expect(screen.queryByRole("alert")).not.toBeInTheDocument();
      view.unmount();
      client.clear();
    });
  }
}
