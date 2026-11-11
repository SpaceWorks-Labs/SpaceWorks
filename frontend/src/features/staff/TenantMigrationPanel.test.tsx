import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { StructuredApiError } from "../../lib/api";
import { TenantMigrationPanel } from "./TenantMigrationPanel";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../lib/api")>("../../lib/api");
  return { ...actual, staffRequest };
});

const digest = "a".repeat(64);
const oldDigest = "b".repeat(64);
const identity = {
  id: 11, username: "ada", email: "ada@example.test", first_name: "Ada",
  last_name: "Maker", display_name: "Ada Maker", phone: "+15550001111",
  date_joined: "2026-01-01T00:00:00Z",
};
const deploymentIdentity = {
  algorithm: "ed25519", deployment_id: "target-deployment", public_key: "public-key",
  fingerprint: "f".repeat(64), age_recipient: "age1target",
};
const baseJob = {
  id: "11111111-1111-1111-1111-111111111111",
  source_archive_digest: digest,
  source_makerspace_id: "7",
  source_makerspace_name: "Forge",
  source_makerspace_slug: "forge",
  source_deployment_id: "source-deployment",
  identity_count: "1",
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
  expires_at: "2026-01-02T00:00:00Z",
  source_retention_notice: "Archives are outside the purge guarantee.",
};
const pairing = {
  id: "22222222-2222-2222-2222-222222222222",
  migration_id: baseJob.id,
  source_tenant_id: "7",
  archive_digest: digest,
  source_deployment_id: "source-deployment",
  source_fingerprint: "s".repeat(64),
  target_deployment_id: "target-deployment",
  target_fingerprint: "t".repeat(64),
  approved_at: "2026-01-01T00:00:00Z",
};
const receipt = {
  payload: { operation: "source_cutover" },
  signer_fingerprint: "s".repeat(64),
  signature: "signature",
};

type ApiState = {
  closureDigest?: string;
  approvals?: unknown[];
  exports?: unknown[];
  imports?: unknown[];
  pairings?: unknown[];
  post?: (path: string, options?: RequestInit) => Promise<unknown> | undefined;
};

function installApi(state: ApiState = {}) {
  staffRequest.mockImplementation((path: string, options?: RequestInit) => {
    if (options?.method === "POST") {
      const result = state.post?.(path, options);
      if (result) return result;
    }
    if (path.endsWith("/disclosure-closure")) return Promise.resolve({ digest: state.closureDigest ?? digest, identities: [identity] });
    if (path.endsWith("/disclosure-approvals")) return Promise.resolve(state.approvals ?? []);
    if (path.endsWith("/exports")) return Promise.resolve(state.exports ?? []);
    if (path.endsWith("/deployment-identity")) return Promise.resolve(deploymentIdentity);
    if (path.endsWith("/pairings")) return Promise.resolve(state.pairings ?? []);
    if (path.endsWith("/imports")) return Promise.resolve(state.imports ?? []);
    if (path.endsWith("/identity-decisions")) return Promise.resolve([identity]);
    if (path.endsWith("/verification")) return Promise.resolve({
      format_version: 1, target_makerspace_id: 99, imported: { hardware: 4 },
      resolved: { users: 1 }, dropped: {}, identities_linked: 1,
      identities_created: 0, external_references_created: 2,
    });
    if (/\/exports\/[^/]+$/.test(path)) return Promise.resolve(state.exports?.[0] ?? {});
    if (/\/imports\/[^/]+$/.test(path)) return Promise.resolve(state.imports?.[0] ?? {});
    return Promise.resolve({});
  });
}

function renderPanel() {
  return render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })}>
      <TenantMigrationPanel makerspace={{ id: 7, name: "Forge", slug: "forge", public_code: "forge", telegram_group_chat_id: "", frontend_domain: null, hidden_from_central_directory: false }} />
    </QueryClientProvider>,
  );
}

const stageLabels = ["review what moves", "link the two servers", "encrypt export", "import & resolve", "verify & materialise", "switch over"];
/** The flow resumes at the furthest recorded stage, so walk from wherever it opened. */
async function goToStep(index: number) {
  for (let guard = 0; guard < 12; guard++) {
    const next = await screen.findByRole("button", { name: /^(Continue to |Review what moves again)/ });
    await waitFor(() => expect(next).toBeEnabled());
    const label = next.textContent ?? "";
    const current = label.startsWith("Review what moves again") ? 5 : stageLabels.indexOf(label.replace(/^Continue to /, "")) - 1;
    if (current === index) return;
    fireEvent.click(current < index ? next : screen.getByRole("button", { name: "Previous step" }));
  }
  throw new Error(`Could not reach step ${index}`);
}
async function confirmAction(title: string) {
  fireEvent.click(await screen.findByRole("button", { name: title + "…" }));
  const dialog = screen.getByRole("dialog");
  fireEvent.change(within(dialog).getByLabelText("Type Forge to confirm"), { target: { value: "Forge" } });
  fireEvent.click(within(dialog).getByRole("button", { name: title }));
}

beforeEach(() => {
  staffRequest.mockReset();
  vi.restoreAllMocks();
});

describe("TenantMigrationPanel disclosure", () => {
  it("keeps unsaved disclosure decisions when moving between stages", async () => {
    installApi(); renderPanel();
    const person = await screen.findByRole("checkbox", { name: /Ada Maker/i });
    fireEvent.click(person);
    fireEvent.click(screen.getByRole("checkbox", { name: /I reviewed every person/i }));
    await goToStep(1);
    expect(screen.queryByRole("checkbox", { name: /Ada Maker/i })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Previous step" }));
    expect(screen.getByRole("checkbox", { name: /Ada Maker/i })).toBeChecked();
    expect(screen.getByRole("checkbox", { name: /I reviewed every person/i })).toBeChecked();
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
  });

  it("renders the exact closure and approves its exact digest and per-person decision", async () => {
    installApi({ post: () => Promise.resolve({ id: "approval", closure_digest: digest, identity_count: "1", approved_count: "1", approved_at: "now" }) });
    renderPanel();

    expect(await screen.findByText("Ada Maker")).toBeVisible();
    expect(screen.getByTestId("closure-digest")).toHaveTextContent(digest);
    fireEvent.click(screen.getByRole("checkbox", { name: /Ada Maker/i }));
    fireEvent.click(screen.getByRole("checkbox", { name: /I reviewed every person/i }));
    fireEvent.click(screen.getByRole("button", { name: "Approve exact closure" }));

    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith(
      "/admin/makerspace/7/tenant-migration/disclosure-approvals",
      { method: "POST", body: JSON.stringify({ digest, decisions: [{ user_id: 11, approved: true }] }) },
    ));
  });

  it("marks a non-revoked approval void when the closure digest changed", async () => {
    installApi({ approvals: [{ id: "old", closure_digest: oldDigest, identity_count: "1", approved_count: "1", approved_at: "now", revoked_at: null }] });
    renderPanel();

    expect(await screen.findByText(/VOID — disclosure closure changed/i)).toBeVisible();
    expect(screen.getByText("Review required")).toBeVisible();
    expect(screen.queryByText("Approved")).not.toBeInTheDocument();
  });

  it("reads a field error from StructuredApiError.body", async () => {
    installApi({ post: () => Promise.reject(new StructuredApiError(400, {
      detail: "Validation failed.", digest: ["Review the newly computed digest."],
    })) });
    renderPanel();
    await screen.findByText("Ada Maker");
    fireEvent.click(screen.getByRole("checkbox", { name: /I reviewed every person/i }));
    fireEvent.click(screen.getByRole("button", { name: "Approve exact closure" }));
    expect(await screen.findByText("Review the newly computed digest.")).toHaveAttribute("role", "alert");
  });
});

describe("TenantMigrationPanel identity decisions", () => {
  it("submits an explicit resolution and membership disposition per person", async () => {
    const job = { ...baseJob, status: "awaiting_identity" };
    installApi({ imports: [job], post: (path) => path.endsWith("/identity-decisions") ? Promise.resolve({ ...job, status: "ready" }) : undefined });
    renderPanel();
    await goToStep(3);
    fireEvent.change(await screen.findByRole("combobox", { name: "Identity resolution for Ada Maker" }), { target: { value: "link_existing" } });
    fireEvent.change(screen.getByRole("spinbutton", { name: "Target user ID for Ada Maker" }), { target: { value: "42" } });
    fireEvent.change(screen.getByRole("combobox", { name: "Membership for Ada Maker" }), { target: { value: "no_membership" } });
    fireEvent.click(screen.getByRole("button", { name: "Submit all identity decisions" }));

    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith(
      `/admin/platform/tenant-migrations/imports/${baseJob.id}/identity-decisions`,
      { method: "POST", body: JSON.stringify({ decisions: [{ source_user_id: "11", identity_resolution: "link_existing", membership_disposition: "no_membership", target_user_id: 42 }] }) },
    ));
  });
});

describe("TenantMigrationPanel deployment pairing", () => {
  it("submits the prefilled target identity unchanged without age_recipient", async () => {
    installApi({ post: (path) => path.endsWith("/pairings") ? Promise.resolve(pairing) : undefined });
    renderPanel();

    await goToStep(1);
    await screen.findByText(/This deployment: target-deployment/);
    fireEvent.click(screen.getByRole("button", { name: "Use this deployment as source" }));
    const sourceInput = screen.getByLabelText("Source deployment identity JSON");
    expect(JSON.parse((sourceInput as HTMLTextAreaElement).value)).not.toHaveProperty("age_recipient");
    fireEvent.change(sourceInput, { target: { value: JSON.stringify({
      algorithm: "ed25519", deployment_id: "source-deployment", public_key: "source-key",
      fingerprint: "s".repeat(64),
    }) } });
    fireEvent.change(screen.getByLabelText("Migration/import job ID"), { target: { value: baseJob.id } });
    fireEvent.change(screen.getByLabelText("Source space ID"), { target: { value: "7" } });
    fireEvent.change(screen.getByLabelText("Archive digest"), { target: { value: digest } });
    fireEvent.click(screen.getByRole("button", { name: "Pin this deployment pairing" }));

    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith(
      "/admin/platform/tenant-migrations/pairings",
      {
        method: "POST",
        body: JSON.stringify({
          migration_id: baseJob.id,
          source_tenant_id: "7",
          archive_digest: digest,
          source: {
            algorithm: "ed25519", deployment_id: "source-deployment",
            public_key: "source-key", fingerprint: "s".repeat(64),
          },
          target: {
            algorithm: "ed25519", deployment_id: "target-deployment",
            public_key: "public-key", fingerprint: "f".repeat(64),
          },
        }),
      },
    ));
  });
});

describe("TenantMigrationPanel cutover", () => {
  const completed = { ...baseJob, status: "completed", target_lifecycle_state: "importing" };
  const exportJob = {
    id: "export-1", status: "available", closure_digest: digest, archive_digest: digest,
    format_version: 1, source_retention_notice: "Archives are outside the purge guarantee.",
    created_at: "now", expires_at: "later",
  };

  it.each(["materializing", "finalizing"])(
    "keeps a %s target visibly IMPORTING while finalization runs",
    async (status) => {
    installApi({ imports: [{ ...baseJob, status }] });
    renderPanel();
    await goToStep(5);
    expect(await screen.findByText("Importing")).toBeVisible();
    expect(screen.getByText(/Import finalization is still running/)).toBeVisible();
    expect(screen.getAllByText(/archives are outside the purge guarantee/i).length).toBeGreaterThan(0);
  });

  it("requires tenant-naming confirmations for every destructive cutover action", async () => {
    installApi({ imports: [completed], exports: [exportJob], pairings: [pairing] });
    renderPanel();
    await goToStep(5);
    fireEvent.change(await screen.findByLabelText("Source switch-over receipt"), { target: { value: JSON.stringify(receipt) } });
    await screen.findByText(/Target makerspace 99/);
    for (const title of ["Pause writes to Forge", "Archive source Forge", "Activate target Forge", "Abort target Forge"]) {
      fireEvent.click(await screen.findByRole("button", { name: title + "…" }));
      const dialog = screen.getByRole("dialog");
      const action = within(dialog).getByRole("button", { name: title });
      expect(action).toBeDisabled();
      fireEvent.change(within(dialog).getByLabelText("Type Forge to confirm"), { target: { value: "Wrong space" } });
      expect(action).toBeDisabled();
      fireEvent.click(within(dialog).getByRole("button", { name: "Cancel" }));
    }
    expect(staffRequest.mock.calls.filter(([, options]) => options?.method === "POST")).toHaveLength(0);
  });

  it("shows IMPORTING before cutover and ACTIVE only after activation", async () => {
    const activated = { ...completed };
    installApi({ imports: [activated], pairings: [pairing], post: (path) => {
      if (!path.endsWith("/activate")) return undefined;
      activated.target_lifecycle_state = "active";
      return Promise.resolve({ message: "active", receipt });
    } });
    vi.spyOn(window, "confirm").mockReturnValue(true);
    renderPanel();
    await goToStep(5);
    expect(await screen.findByText("Importing")).toBeVisible();
    await screen.findByText("imported");
    expect(screen.getByRole("region", { name: "Import verification report" })).toHaveTextContent("imported");
    fireEvent.change(await screen.findByLabelText("Source switch-over receipt"), { target: { value: JSON.stringify(receipt) } });
    await confirmAction("Activate target Forge");
    expect(await screen.findByText("Active")).toBeVisible();
    expect(screen.queryByText("Importing")).not.toBeInTheDocument();
  });

  it("shows ABORTED distinctly and exposes the target abort receipt", async () => {
    const aborted = { ...completed };
    installApi({ imports: [aborted], pairings: [pairing], post: (path) => {
      if (!path.endsWith("/abort")) return undefined;
      aborted.target_lifecycle_state = "aborted";
      return Promise.resolve({ message: "aborted", receipt });
    } });
    vi.spyOn(window, "confirm").mockReturnValue(true);
    renderPanel();
    await goToStep(5);
    await confirmAction("Abort target Forge");
    expect(await screen.findByText("Aborted")).toBeVisible();
    expect(screen.getByLabelText(/Target abort receipt/)).toHaveValue(JSON.stringify(receipt, null, 2));
  });

  it("uses persisted ACTIVE state after reload and hides one-way cutover actions", async () => {
    installApi({
      imports: [{ ...completed, target_lifecycle_state: "active" }],
      pairings: [pairing],
    });
    renderPanel();
    await goToStep(5);

    expect(await screen.findByText("Active")).toBeVisible();
    expect(screen.queryByRole("button", { name: /Activate target/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Abort target/ })).not.toBeInTheDocument();
  });
});

describe("TenantMigrationPanel resume", () => {
  it("opens at the furthest recorded stage and keeps completed stages selectable", async () => {
    installApi({ imports: [{ ...baseJob, status: "ready" }], pairings: [pairing] });
    renderPanel();
    expect(await screen.findByRole("button", { name: "Continue to switch over" })).toBeEnabled();
    expect(screen.getByText("Per-person identity decisions")).toBeVisible();
    expect(screen.getByRole("button", { name: "Run reviewed import" })).toBeDisabled();
  });

  it("keeps the flow usable when deployment pairings fail to load", async () => {
    staffRequest.mockImplementation((path: string) => path.endsWith("/pairings") ? Promise.reject(new Error("down"))
      : path.endsWith("/disclosure-closure") ? Promise.resolve({ digest, identities: [identity] }) : Promise.resolve([]));
    renderPanel();
    expect(await screen.findByText("Ada Maker")).toBeVisible();
    expect(screen.getByText(/Couldn't load server links/)).toBeVisible();
  });
});
