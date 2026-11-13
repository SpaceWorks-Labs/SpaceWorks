// SKIPPED (not run, not type-checked): imported from a development worktree, kept for reference.
// Reason: Not in release 0.12.0: WhatsAppTemplateBindings component is not in release 0.12.0.
// Excluded from vitest (vite.config.ts) and outside tsconfig "include"; rewrite against the release code before moving back under src/.
import { afterEach, expect, it, vi } from "vitest";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { WhatsAppTemplateBindings } from "./WhatsAppTemplateBindings";
import { messagingBinding, messagingCatalog, messagingFailure, messagingFetch, renderMessaging } from "../../test/messagingFixtures";
import { expectNoA11yViolations } from "../../test/axe";

afterEach(() => vi.unstubAllGlobals());
const page = { count: 1, next: null, previous: null, results: [messagingBinding] };

it("lists review status and edits only allowed ordered BODY parameters", async () => {
  const writes: unknown[] = [];
  messagingFetch((url, options) => {
    if (options.method === "PATCH") { writes.push(JSON.parse(String(options.body))); return messagingBinding; }
    return url.pathname.endsWith("/catalog") ? messagingCatalog : page;
  });
  const { container } = renderMessaging(<WhatsAppTemplateBindings makerspaceId={11} />);
  await screen.findByText("Needs review");
  expect(screen.getByText(/business account changed or this binding was imported/)).toBeInTheDocument();
  expect(screen.getByText(/Only positional text BODY parameters/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Edit request_accepted" }));
  expect(screen.getByLabelText("BODY parameter 1")).toHaveValue("makerspace_name");
  const allowed = [...(screen.getByLabelText("BODY parameter 1") as HTMLSelectElement).options].map(option => option.value);
  expect(allowed).toEqual(["makerspace_name", "request_id"]);
  fireEvent.click(screen.getByRole("button", { name: "Move parameter 2 up" }));
  expect(screen.getByLabelText("BODY parameter 1")).toHaveValue("request_id");
  fireEvent.click(screen.getByLabelText("Active binding"));
  await expectNoA11yViolations(container);
  fireEvent.click(screen.getByRole("button", { name: "Save binding" }));
  await waitFor(() => expect(writes).toEqual([{ feature: "hardware_requests", event: "accepted", audience: "staff",
    template_name: "request_accepted", language: "en", parameters: ["request_id", "makerspace_name"], is_active: true }]));
});

it("validates before creation, resets variables on audience change, and supports deletion", async () => {
  const writes: { method: string; body?: unknown; path: string }[] = [];
  let rows = { ...page, count: 0, results: [] as typeof page.results };
  messagingFetch((url, options) => {
    if (options.method === "POST") {
      writes.push({ method: "POST", path: url.pathname, body: JSON.parse(String(options.body)) });
      rows = page; return messagingBinding;
    }
    if (options.method === "DELETE") { writes.push({ method: "DELETE", path: url.pathname }); rows = { ...page, results: [], count: 0 }; return new Response(null, { status: 204 }); }
    return url.pathname.endsWith("/catalog") ? messagingCatalog : rows;
  });
  renderMessaging(<WhatsAppTemplateBindings makerspaceId={11} />);
  await screen.findByText("No template bindings yet.");
  fireEvent.click(screen.getByRole("button", { name: "Add template binding" }));
  fireEvent.change(screen.getByLabelText("Template name"), { target: { value: "INVALID name" } });
  fireEvent.click(screen.getByRole("button", { name: "Save binding" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("lowercase template name");
  expect(writes).toEqual([]);
  fireEvent.click(screen.getByRole("button", { name: "Add BODY parameter" }));
  fireEvent.change(screen.getByLabelText("Feature / event / audience"), { target: { value: "hardware_requests:accepted:member" } });
  expect(screen.queryByLabelText("BODY parameter 1")).not.toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Template name"), { target: { value: "request_accepted" } });
  fireEvent.change(screen.getByLabelText("Template language"), { target: { value: "hi" } });
  fireEvent.click(screen.getByRole("button", { name: "Add BODY parameter" }));
  fireEvent.click(screen.getByRole("button", { name: "Save binding" }));
  await waitFor(() => expect(writes[0]?.body).toEqual({ feature: "hardware_requests", event: "accepted", audience: "member",
    template_name: "request_accepted", language: "hi", parameters: ["request_id"], is_active: true }));
  const remove = await screen.findByRole("button", { name: "Delete request_accepted" });
  fireEvent.click(remove);
  await screen.findByText("No template bindings yet.");
  expect(writes[1]).toMatchObject({ method: "DELETE", path: "/api/v1/admin/makerspace/11/whatsapp-templates/7" });
});

it("shows provider validation failures without discarding the draft", async () => {
  messagingFetch((url, options) => options.method === "PATCH"
    ? messagingFailure(400, { template_name: ["Template must be approved in Meta."] })
    : url.pathname.endsWith("/catalog") ? messagingCatalog : page);
  renderMessaging(<WhatsAppTemplateBindings makerspaceId={11} />);
  fireEvent.click(await screen.findByRole("button", { name: "Edit request_accepted" }));
  fireEvent.click(screen.getByRole("button", { name: "Save binding" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Template must be approved in Meta.");
  expect(screen.getByLabelText("Template name")).toHaveValue("request_accepted");
});

it("paginates bindings using the local endpoint and offers read-error retry", async () => {
  const fetcher = messagingFetch(url => url.pathname.endsWith("/catalog") ? messagingCatalog
    : url.searchParams.get("page") === "2" ? { count: 25, next: null, previous: "https://api.example/previous", results: [{ ...messagingBinding, id: 8, template_name: "second_page" }] }
      : { ...page, count: 25, next: "https://api.example/next" });
  renderMessaging(<WhatsAppTemplateBindings makerspaceId={11} />);
  fireEvent.click(await screen.findByRole("button", { name: "Next templates" }));
  await screen.findByRole("button", { name: "Edit second_page" });
  expect(fetcher.mock.calls.some(([url]) => String(url).endsWith("whatsapp-templates?page=2"))).toBe(true);
});
