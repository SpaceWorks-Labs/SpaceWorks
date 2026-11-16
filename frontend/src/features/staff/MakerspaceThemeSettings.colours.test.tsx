import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { staffRequest } from "../../lib/api";
import { MakerspaceThemeSettings } from "./MakerspaceThemeSettings";
import type { Makerspace } from "./StaffPanels";

vi.mock("../../lib/api", () => ({ staffRequest: vi.fn() }));
vi.mock("../auth/SampleIdCard", () => ({ SampleIdCard: () => <div data-testid="sample-id-card" /> }));
// "#123456" stands in for a combination the API would refuse, which the derivation itself never produces.
vi.mock("../../lib/brandColours", async (importOriginal) => {
  const real = await importOriginal<typeof import("../../lib/brandColours")>();
  return { ...real, brandContrastReport: (value: unknown) => {
    const report = real.brandContrastReport(value);
    const bad = (value as Record<string, string>)?.primary_color === "#123456";
    return bad ? { ...report, failures: [{ mode: "dark", pair: "brand-ink on panel", ratio: 3.1, minimum: 4.5 }] } : report;
  } };
});
afterEach(() => { vi.clearAllMocks(); });

const space = { id: 7, name: "Brand", slug: "brand" } as Makerspace;
const settings = (primary = "", accent = "") => ({ ...space, theme_config: { mode: "light", primary_color: primary, accent_color: accent, logo_url: "" } });

function show(saved = settings()) {
  const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
  return render(<QueryClientProvider client={client}><MakerspaceThemeSettings makerspace={space} settings={saved} loading={false} /></QueryClientProvider>);
}
const brand = (surface: string, mode: "light" | "dark") => screen.getByTestId(`preview-${surface}-${mode}`).style.getPropertyValue("--color-brand");

const all = () => fireEvent.click(screen.getByRole("tab", { name: "All" }));

it("shows one audience at a time, grouped by who sees it, and All stacks them", async () => {
  show();
  expect(screen.getByRole("tab", { name: "Member app" })).toHaveAttribute("aria-selected", "true");
  expect(screen.getAllByRole("region").filter((el) => el.hasAttribute("data-surface")).map((el) => el.getAttribute("data-surface"))).toEqual(["member"]);
  fireEvent.keyDown(screen.getByRole("tab", { name: "Member app" }), { key: "ArrowRight" });
  expect(screen.getByRole("tab", { name: "Public pages" })).toHaveAttribute("aria-selected", "true");
  all();
  const sections = screen.getAllByRole("region").filter((el) => el.hasAttribute("data-surface"));
  expect(sections.map((el) => el.getAttribute("data-surface"))).toEqual(["member", "public", "printed", "screens", "staff"]);
  expect(within(sections[4]).getByText(/Space Manager, Inventory Manager, Machine Manager/)).toBeVisible();
  expect(within(sections[4]).getByText(/No space colours/)).toBeVisible();
  expect(within(sections[2]).getByText(/ID cards, certificates and wallet passes keep their own colours/)).toBeVisible();
  for (const id of ["staff", "member", "public", "screens"]) for (const mode of ["light", "dark"]) expect(screen.getByTestId(`preview-${id}-${mode}`)).toBeInTheDocument();
  expect(await screen.findByTestId("sample-id-card")).toBeInTheDocument();
});

it("previews follow the draft with the app's own variables; staff never changes", () => {
  show();
  all();
  fireEvent.change(screen.getByLabelText("Primary fill"), { target: { value: "#1d5fa8" } });
  for (const surface of ["member", "public"]) for (const mode of ["light", "dark"] as const) expect(brand(surface, mode)).toBe("29 95 168");
  expect(brand("staff", "light")).toBe("");
  expect(screen.getByTestId("preview-staff-dark").style.getPropertyValue("--color-bg")).toBe("0 0 0");
  fireEvent.change(screen.getByLabelText("Link colour seed"), { target: { value: "#ff7447" } });
  expect(screen.getByTestId("receipt-light")).toHaveAttribute("data-accent", "#ff7447");
});

it("saves the default look for visitors and screens with the colours", async () => {
  vi.mocked(staffRequest).mockResolvedValue(space);
  show();
  expect(screen.getByRole("radio", { name: "Light" })).toBeChecked();
  fireEvent.click(screen.getByRole("radio", { name: "Solid black" }));
  fireEvent.click(screen.getByRole("button", { name: "Save changes" }));
  await waitFor(() => expect(staffRequest).toHaveBeenCalledTimes(1));
  expect(JSON.parse(vi.mocked(staffRequest).mock.calls[0][1]!.body as string).theme_config).toMatchObject({ mode: "dark", primary_color: "", accent_color: "" });
});

it("clears either colour field", () => {
  show(settings("#004400", "#5a1633"));
  fireEvent.click(screen.getByRole("button", { name: "Clear Link colour seed" }));
  expect(screen.getByLabelText("Link colour seed")).toHaveValue("");
  expect(screen.getByLabelText("Primary fill")).toHaveValue("#004400");
  expect(screen.getByRole("button", { name: "Clear Link colour seed" })).toBeDisabled();
});

it("applies a preset, then resets to the Space Works default", () => {
  show(settings("#004400"));
  fireEvent.click(screen.getByRole("button", { name: "Plum" }));
  expect(screen.getByLabelText("Primary fill")).toHaveValue("#9a3f88");
  expect(screen.getByRole("button", { name: "Plum" })).toHaveAttribute("aria-pressed", "true");
  fireEvent.click(screen.getByRole("button", { name: "Reset to Space Works default" }));
  expect(screen.getByLabelText("Primary fill")).toHaveValue("");
  expect(screen.getByRole("button", { name: "Reset to Space Works default" })).toBeDisabled();
});

it("shows the unsaved bar only when dirty and discards", () => {
  show();
  expect(screen.queryByRole("button", { name: "Save changes" })).toBeNull();
  fireEvent.change(screen.getByLabelText("Primary fill"), { target: { value: "#004400" } });
  expect(screen.getByRole("button", { name: "Save changes" })).toBeEnabled();
  fireEvent.click(screen.getByRole("button", { name: "Discard" }));
  expect(screen.getByLabelText("Primary fill")).toHaveValue("");
  expect(screen.queryByRole("button", { name: "Save changes" })).toBeNull();
});

it("offers a fix for a fill that vanishes on solid black, and applying it clears the advice", () => {
  show();
  fireEvent.change(screen.getByLabelText("Primary fill"), { target: { value: "#142c2a" } });
  expect(screen.getByText(/Advice does not block saving/)).toBeVisible();
  expect(screen.getByRole("button", { name: "Save changes" })).toBeEnabled();
  fireEvent.click(screen.getByRole("button", { name: /^Fix it: use #[0-9a-f]{6} for Primary fill$/ }));
  expect(screen.getByLabelText("Primary fill")).not.toHaveValue("#142c2a");
  expect(screen.getByText("All checked pairs meet WCAG AA in both modes.")).toBeVisible();
});

it("blocks saving a combination the API would refuse", () => {
  show();
  fireEvent.change(screen.getByLabelText("Primary fill"), { target: { value: "#123456" } });
  expect(screen.getByText(/Saving is blocked until the required checks pass/)).toBeVisible();
  expect(screen.getAllByText(/Solid black: brand-ink on panel/)[0]).toBeVisible();
  expect(screen.getByRole("button", { name: "Save changes" })).toBeDisabled();
  fireEvent.submit(screen.getByRole("button", { name: "Save changes" }).closest("form")!);
  expect(staffRequest).not.toHaveBeenCalled();
});

it("undoes the last save by writing the previous colours back", async () => {
  vi.mocked(staffRequest).mockResolvedValue(space);
  const view = show(settings("#004400"));
  fireEvent.change(screen.getByLabelText("Primary fill"), { target: { value: "#1d5fa8" } });
  fireEvent.click(screen.getByRole("button", { name: "Save changes" }));
  await waitFor(() => expect(staffRequest).toHaveBeenCalledTimes(1));
  view.rerender(<QueryClientProvider client={new QueryClient()}><MakerspaceThemeSettings makerspace={space} settings={settings("#1d5fa8")} loading={false} /></QueryClientProvider>);
  fireEvent.click(await screen.findByRole("button", { name: "Undo last save" }));
  await waitFor(() => expect(staffRequest).toHaveBeenCalledTimes(2));
  expect(JSON.parse(vi.mocked(staffRequest).mock.calls[1][1]!.body as string).theme_config.primary_color).toBe("#004400");
});

it("labels the picker, hex field and clear control for keyboard and screen-reader use", () => {
  show(settings("#004400"));
  expect(screen.getByLabelText("Primary fill picker")).toHaveAttribute("type", "color");
  expect(screen.getByLabelText("Primary fill")).toHaveAccessibleDescription(/Buttons and filled areas/);
  fireEvent.click(screen.getByRole("button", { name: "Clear Primary fill" }));
  expect(screen.getByLabelText("Primary fill")).toHaveValue("");
});
