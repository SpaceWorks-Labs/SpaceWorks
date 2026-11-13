import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import type { ReactNode } from "react";
import { expect, it, vi } from "vitest";
import { PublicPrintRequestPage } from "./PublicPrintRequestPage";

const availability = vi.hoisted(() => ({ printing: true, jobs: false }));
const api = vi.hoisted(() => ({ fetchPrintQueues: vi.fn(), fetchPublicConsumablePools: vi.fn(), fetchPrintStatus: vi.fn(), presignPrintUpload: vi.fn(), submitPrintRequest: vi.fn(), uploadToStorage: vi.fn() }));
vi.mock("./publicApi", () => api);
vi.mock("../../lib/tenant", () => ({ useTenant: () => ({ mode: "single", slug: "lab", modules: new Set(["membership", "presence", ...(availability.printing ? ["machine_service"] : [])]), bootstrap: { makerspace: { slug: "lab", name: "Lab" }, modules: ["membership", "presence", ...(availability.printing ? ["machine_service"] : [])], features: availability.jobs ? ["machines.job_requests"] : [], branding: {} } }), useTenantPath: () => (path = "") => `/m/lab/${path}` }));
vi.mock("../../lib/useTenantBranding", () => ({ useTenantBranding: () => ({}) }));
vi.mock("../inventory/usePublicInventory", () => ({ useTenantBootstrap: () => ({}) }));
vi.mock("../../lib/publicHome", () => ({ publicFamilies: () => [] }));
vi.mock("../../components/layouts", () => ({ PublicLayout: ({ children }: { children: ReactNode }) => <>{children}</>, PublicDetailLayout: ({ sections, actionCard }: { sections: { content: ReactNode }[]; actionCard: { form: ReactNode } }) => <>{sections.map((section, index) => <div key={index}>{section.content}</div>)}{actionCard.form}</> }));
vi.mock("./PublicPrintRequestPanels", () => ({ PrintStatusPanel: ({ publicToken }: { publicToken?: string }) => <p>Tracking {publicToken}</p> }));
vi.mock("./PublicPrintRequestForm", async original => ({ ...(await original<object>()), PrintDetailsForm: () => <p>New print form</p> }));
vi.mock("../payments/PricePreview", () => ({ PricePreview: () => null }));

it("keeps existing print tracking but does not load or offer a new form when job requests are off", async () => {
  availability.printing = true; availability.jobs = false;
  api.fetchPrintQueues.mockReset(); api.fetchPublicConsumablePools.mockReset(); api.fetchPrintStatus.mockReset();
  api.fetchPrintStatus.mockResolvedValue({ status: "pending" });
  window.history.replaceState({}, "", "/m/lab/print?token=private-token");
  render(<MemoryRouter><QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><PublicPrintRequestPage /></QueryClientProvider></MemoryRouter>);
  expect(await screen.findByText("Online machine requests aren't available here. Ask space staff for help.")).toBeInTheDocument();
  expect(await screen.findByText("Tracking private-token")).toBeInTheDocument();
  await waitFor(() => expect(api.fetchPrintStatus).toHaveBeenCalledWith("private-token"));
  expect(api.fetchPrintQueues).not.toHaveBeenCalled(); expect(api.fetchPublicConsumablePools).not.toHaveBeenCalled();
  expect(api.presignPrintUpload).not.toHaveBeenCalled(); expect(api.submitPrintRequest).not.toHaveBeenCalled();
  expect(screen.queryByText("New print form")).toBeNull();
});


it("does not query or offer print tracking when machine service (which holds the print queue) is off", async () => {
  availability.printing = false; availability.jobs = true;
  api.fetchPrintQueues.mockReset(); api.fetchPublicConsumablePools.mockReset(); api.fetchPrintStatus.mockReset();
  api.fetchPrintStatus.mockResolvedValue({ status: "pending" });
  window.history.replaceState({}, "", "/m/lab/print?token=private-token");
  render(<MemoryRouter><QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><PublicPrintRequestPage /></QueryClientProvider></MemoryRouter>);
  expect(await screen.findByText("Print tracking isn’t available here right now. Ask space staff for help.")).toBeInTheDocument();
  expect(api.fetchPrintStatus).not.toHaveBeenCalled();
  expect(screen.queryByText("Tracking private-token")).toBeNull();
  expect(screen.queryByText("New print form")).toBeNull();
  expect(api.fetchPrintQueues).not.toHaveBeenCalled(); expect(api.fetchPublicConsumablePools).not.toHaveBeenCalled();
  expect(api.presignPrintUpload).not.toHaveBeenCalled(); expect(api.submitPrintRequest).not.toHaveBeenCalled();
});
