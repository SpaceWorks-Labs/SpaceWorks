import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { StructuredApiError } from "../../lib/api";
import { TenantProvider } from "../../lib/tenant";
import { expectNoA11yViolations } from "../../test/axe";
import { JobRequestPage } from "./JobRequestPage";
import type { JobType } from "./types";

const api = vi.hoisted(() => ({ fetchJobTypes: vi.fn(), stageJobFile: vi.fn(), submitJob: vi.fn() }));
vi.mock("./api", async original => ({ ...(await original<object>()), ...api }));
const fetchPools = vi.hoisted(() => vi.fn());
const identity = vi.hoisted(() => ({ signedOut: false }));
const availability = vi.hoisted(() => ({ modules: ["machine_service", "membership", "presence"], features: ["machines.job_requests"] }));
vi.mock("./useMemberIdentity", () => ({ useMemberIdentity: () => ({ restoring: false, loading: false, signedOut: identity.signedOut,
  identity: { refetch: vi.fn(), data: { username: "ada" } } }) }));
vi.mock("../inventory/usePublicInventory", () => ({ useTenantBootstrap: () => ({ isLoading: false, isError: false, data: {
  makerspace: { id: 1, slug: "lab", name: "Lab", logo_url: null }, branding: { display_name: "Lab" },
  modules: availability.modules, features: availability.features } }) }));
vi.mock("../printing/publicApi", async original => ({ ...(await original<object>()), fetchPublicConsumablePools: fetchPools }));
vi.mock("../payments/PricePreview", () => ({ PricePreview: () => null }));
vi.mock("../members/MemberAuthPanel", () => ({ MemberAuthPanel: () => <p>Sign in panel</p> }));

const printer: JobType = { queue_id: 3, name: "3D printing", machine_type_id: 9, machine_type_name: "3D printer", machine_type_slug: "3d-printer",
  is_printer: true, file_groups: ["fab-3dprint"], accepted_extensions: [".stl", "3mf"], quotes: "auto", prepay: false, runs_unattended: true, max_open_jobs: 2 };
const laser: JobType = { ...printer, queue_id: 5, name: "Laser cutting", machine_type_id: 11, machine_type_name: "Laser cutter",
  machine_type_slug: "laser", is_printer: false, accepted_extensions: ["svg", "dxf"], quotes: "off", runs_unattended: false, max_open_jobs: null };

function show(url = "/m/lab/machine-jobs/new?type=printer") {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter initialEntries={[url]}><TenantProvider><Routes>
      <Route path="/m/:slug/machine-jobs/new" element={<JobRequestPage />} />
      <Route path="/m/:slug/member/machine-jobs/:jobId" element={<p>Job page</p>} />
      <Route path="/m/:slug/machines" element={<p>Machines page</p>} />
    </Routes></TenantProvider></MemoryRouter></QueryClientProvider>);
}

async function fillToConfirm() {
  fireEvent.change(await screen.findByLabelText("Design files"), { target: { files: [new File(["solid"], "part.stl")] } });
  fireEvent.click(screen.getByRole("button", { name: "Next: details" }));
  fireEvent.change(await screen.findByLabelText("Title"), { target: { value: "Bracket" } });
  fireEvent.click(screen.getByRole("button", { name: "Next: confirm" }));
  for (const box of await screen.findAllByRole("checkbox")) fireEvent.click(box);
}

describe("JobRequestPage", () => {
  beforeEach(() => {
    Object.values(api).forEach(fn => fn.mockReset());
    availability.modules = ["machine_service", "membership", "presence"];
    availability.features = ["machines.job_requests"];
    fetchPools.mockReset(); fetchPools.mockResolvedValue([]);
    identity.signedOut = false;
    api.fetchJobTypes.mockResolvedValue([printer, laser]);
    api.stageJobFile.mockResolvedValue(91);
    api.submitJob.mockResolvedValue({ id: 77, public_token: "tok", status: "pending" });
  });

  it.each(["membership", "presence"])("offers a staff handoff and no job requests when %s is off", async missing => {
    availability.modules = availability.modules.filter(key => key !== missing);
    show();
    expect(await screen.findByText("Online machine requests aren't available here. Ask space staff for help.")).toBeInTheDocument();
    expect(api.fetchJobTypes).not.toHaveBeenCalled(); expect(api.stageJobFile).not.toHaveBeenCalled(); expect(api.submitJob).not.toHaveBeenCalled();
  });

  it("offers no new job flow when the job-request capability is off", async () => {
    availability.features = [];
    show();
    expect(await screen.findByText("Online machine requests aren't available here. Ask space staff for help.")).toBeInTheDocument();
    expect(api.fetchJobTypes).not.toHaveBeenCalled(); expect(api.stageJobFile).not.toHaveBeenCalled(); expect(api.submitJob).not.toHaveBeenCalled();
  });

  it("offers a generic printer job without fetching printing pools when Printing is off", async () => {
    show();
    await fillToConfirm();
    expect(screen.getByRole("button", { name: "Send request" })).toBeEnabled();
    expect(fetchPools).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Send request" }));
    expect(await screen.findByText("Job page")).toBeInTheDocument();
    expect(api.submitJob).toHaveBeenCalledWith("lab", expect.objectContaining({ queue_id: 3, title: "Bracket" }));
    expect(fetchPools).not.toHaveBeenCalled();
  });

  it("omits a previously selected pool when Printing turns off during upload", async () => {
    availability.modules = [...availability.modules, "printing"];
    fetchPools.mockResolvedValue([{ id: 42, material: "PLA", color: "Blue" }]);
    let finishUpload!: (value: number) => void;
    api.stageJobFile.mockImplementation(() => new Promise<number>(resolve => { finishUpload = resolve; }));
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const view = () => <QueryClientProvider client={client}><MemoryRouter initialEntries={["/m/lab/machine-jobs/new?type=printer"]}><TenantProvider><Routes>
      <Route path="/m/:slug/machine-jobs/new" element={<JobRequestPage />} />
      <Route path="/m/:slug/member/machine-jobs/:jobId" element={<p>Job page</p>} />
    </Routes></TenantProvider></MemoryRouter></QueryClientProvider>;
    const rendered = render(view());
    fireEvent.change(await screen.findByLabelText("Design files"), { target: { files: [new File(["solid"], "part.stl")] } });
    fireEvent.click(screen.getByRole("button", { name: "Next: details" }));
    fireEvent.change(await screen.findByLabelText("Title"), { target: { value: "Bracket" } });
    fireEvent.change(await screen.findByLabelText("Filament in stock"), { target: { value: "42" } });
    fireEvent.click(screen.getByRole("button", { name: "Next: confirm" }));
    for (const box of await screen.findAllByRole("checkbox")) fireEvent.click(box);
    expect(screen.getByRole("button", { name: "Send request" })).toBeEnabled();
    fireEvent.click(screen.getByRole("button", { name: "Send request" }));
    await waitFor(() => expect(api.stageJobFile).toHaveBeenCalledTimes(1));
    availability.modules = availability.modules.filter(key => key !== "printing");
    rendered.rerender(view());
    finishUpload(91);
    expect(await screen.findByText("Job page")).toBeInTheDocument();
    expect(api.submitJob).toHaveBeenCalledWith("lab", expect.objectContaining({ consumable_pool_id: null }));
  });

  it("lists every type with its formats, quote and unattended hints", async () => {
    const { container } = show("/m/lab/machine-jobs/new");
    expect(await screen.findByText("Accepts .stl, .3mf")).toBeInTheDocument();
    expect(screen.getByText("Accepts .svg, .dxf")).toBeInTheDocument();
    expect(screen.getByText(/you approve a quote before it joins the queue/)).toBeInTheDocument();
    expect(screen.getByText(/Runs unattended/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Next: files" })).toBeDisabled();
    fireEvent.click(screen.getByRole("radio", { name: /Laser cutting/ }));
    expect(screen.getByRole("button", { name: "Next: files" })).toBeEnabled();
    await expectNoA11yViolations(container);
  });

  it("preselects the printer, flags a wrong file, then stages, submits and opens the job", async () => {
    show();
    const input = await screen.findByLabelText("Design files");
    fireEvent.change(input, { target: { files: [new File(["x"], "notes.txt")] } });
    expect(screen.getByText("This machine doesn't take .txt files.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Next: details" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Remove notes.txt" }));
    await fillToConfirm();
    fireEvent.click(screen.getByRole("button", { name: "Send request" }));
    expect(await screen.findByText("Job page")).toBeInTheDocument();
    expect(api.stageJobFile).toHaveBeenCalledWith("lab", 3, expect.any(File), "model");
    expect(api.submitJob).toHaveBeenCalledWith("lab", expect.objectContaining({ queue_id: 3, title: "Bracket", file_ids: [91], copies: 1,
      own_material: false, acknowledgements: { pickup_policy: true, failure_policy: true, own_content: true } }));
  });

  it("explains a presence refusal and re-uses the staged file on retry", async () => {
    api.submitJob.mockRejectedValueOnce(new StructuredApiError(403, { detail: "Check in first.", code: "presence_required" }));
    show();
    await fillToConfirm();
    fireEvent.click(screen.getByRole("button", { name: "Send request" }));
    expect(await screen.findByText("Check in at the space first, then send your request.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Check in →" })).toHaveAttribute("href", "/m/lab/member");
    fireEvent.click(screen.getByRole("button", { name: "Send request" }));
    expect(await screen.findByText("Job page")).toBeInTheDocument();
    expect(api.stageJobFile).toHaveBeenCalledTimes(1);
  });

  it("returns to the files step with each refused file's own error", async () => {
    api.stageJobFile.mockRejectedValueOnce(new StructuredApiError(400, { file: "This file type is not accepted for this machine.", code: "extension" }));
    show();
    await fillToConfirm();
    fireEvent.click(screen.getByRole("button", { name: "Send request" }));
    expect(await screen.findByText("This file type is not accepted for this machine.")).toBeInTheDocument();
    expect(screen.getByLabelText("Design files")).toBeInTheDocument();
    expect(api.submitJob).not.toHaveBeenCalled();
  });

  it("asks a signed-out visitor to sign in, and says when the space takes no jobs", async () => {
    identity.signedOut = true;
    const first = show();
    expect(screen.getByText("Sign in panel")).toBeInTheDocument();
    first.unmount();
    identity.signedOut = false;
    api.fetchJobTypes.mockRejectedValue(new StructuredApiError(404, { detail: "off", code: "capability_disabled" }));
    show();
    expect(await screen.findByText("Lab isn't taking job requests right now.")).toBeInTheDocument();
  });
});
