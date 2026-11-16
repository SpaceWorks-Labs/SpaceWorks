import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { Suspense, type ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { BackupRestorePanel } from "../BackupRestorePanel";
import { PlatformDataPage } from "./PlatformDataPage";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../../lib/api")>("../../../lib/api");
  return { ...actual, staffRequest };
});

function mount(node: ReactNode, url = "/admin/platform-data") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  return render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[url]}>
    <Suspense fallback={null}>{node}</Suspense>
  </MemoryRouter></QueryClientProvider>);
}

beforeEach(() => {
  staffRequest.mockReset();
  staffRequest.mockImplementation(async (path: string) => {
    if (path.endsWith("/pairings") || path.endsWith("/imports")) return [];
    if (path.endsWith("/deployment-identity")) return { algorithm: "ed25519", deployment_id: "target", public_key: "k", fingerprint: "f".repeat(64), age_recipient: "age1" };
    return {};
  });
});

describe("Data & recovery › Import a space (0.12.0 row 22)", () => {
  it("offers the target-side import without a chosen space", async () => {
    mount(<PlatformDataPage />, "/admin/platform-data?section=space-import");
    expect(await screen.findByRole("heading", { name: "Import a space" })).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: "Create target import" })).toBeInTheDocument();
    // Only platform-wide routes: nothing under /admin/makerspace/<id>/.
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/platform/tenant-migrations/imports"));
    expect(staffRequest.mock.calls.some(([path]) => String(path).includes("/admin/makerspace/"))).toBe(false);
  });

  it("switches to pinning the source deployment", async () => {
    mount(<PlatformDataPage />, "/admin/platform-data?section=space-import");
    fireEvent.click(await screen.findByRole("radio", { name: "Link the two servers" }));
    expect(screen.queryByRole("button", { name: "Create target import" })).toBeNull();
  });

  it("is absent when the deployment does not ship tenant migration", () => {
    mount(<PlatformDataPage unavailableApps={["tenant_migration"]} />);
    expect(screen.queryByRole("link", { name: "Import a space" })).toBeNull();
  });
});

describe("BackupRestorePanel without a space (0.12.0 row 23)", () => {
  it("renders no per-space sections when no makerspace id is given", () => {
    mount(<BackupRestorePanel isSuperadmin={false} />);
    expect(screen.getByRole("heading", { name: "Backup & restore" })).toBeInTheDocument();
    expect(screen.queryByText("This space")).toBeNull();
    expect(screen.queryByText("Move to your own server")).toBeNull();
  });
});
