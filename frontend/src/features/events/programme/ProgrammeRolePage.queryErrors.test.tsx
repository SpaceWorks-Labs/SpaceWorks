import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";
import { memberRequest, StructuredApiError } from "../../../lib/api";
import { programmeKey } from "../contributions/api";
import type { ProgrammeContext } from "../contracts/types";
import fixture from "../../../../../backend/tests/events/programme/contracts/fixtures/public-url-bootstrap-v3.json";
import { ProgrammeRolePage } from "./ProgrammeRolePage";
import { sessionScope } from "../../staff/eventProgramme/sessionScope";

vi.mock("../../../lib/api", async original => ({ ...await original<typeof import("../../../lib/api")>(), memberRequest: vi.fn() }));
vi.mock("../contributions/RoleApplicationForm", () => ({ RoleApplicationForm: () => <form aria-label="Role application">Private application form</form> }));
vi.mock("../../staff/eventProgramme/sessionScope", async original => ({
  ...await original<typeof import("../../staff/eventProgramme/sessionScope")>(), sessionScope: vi.fn(),
}));
beforeEach(() => { vi.mocked(sessionScope).mockReturnValue(["localhost", "person", "session-1"]); });

it.each([[403, 503], [503, 403], [503, 503]] as const)(
  "retries failed role reads independently (application %s, posting %s) and hides the form", async (applicationStatus, postingStatus) => {
    const scope = { eventId: 8, makerspaceId: 3, accountId: 17 };
    const context = fixture.context as unknown as ProgrammeContext;
    const paths = { application: "/role-applications/4/", posting: "/role-postings/9/" };
    const attempts = { application: 0, posting: 0 };
    let failed = false;
    const code = (status: number) => status === 403 ? "permission_denied" : "service_unavailable";
    vi.mocked(memberRequest).mockReset().mockImplementation(async path => {
      const kind = path.endsWith(paths.application) ? "application" : "posting";
      attempts[kind]++;
      if (failed) {
        const status = kind === "application" ? applicationStatus : postingStatus;
        throw new StructuredApiError(status, { code: code(status), detail: `${kind} ${code(status)}` });
      }
      return { id: kind === "application" ? 4 : 9, event_id: 8, posting_id: 9, version: 1, state: "draft", allowed_actions: [] };
    });
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<QueryClientProvider client={client}><MemoryRouter><ProgrammeRolePage scope={scope} context={context}
      applicationId={4} base="/programme" /></MemoryRouter></QueryClientProvider>);
    await screen.findByRole("form", { name: "Role application" });
    failed = true;
    await act(async () => { await client.refetchQueries(); });
    await waitFor(() => expect(screen.getAllByRole("alert")).toHaveLength(2));
    for (const kind of ["application", "posting"] as const) {
      const state = client.getQueryState([...programmeKey(scope, "member"), paths[kind]]);
      const status = kind === "application" ? applicationStatus : postingStatus;
      const alert = within(screen.getAllByRole("alert")[kind === "application" ? 0 : 1]);
      expect(alert.getByText(`${kind} ${code(status)}`, { exact: true })).toBeVisible();
      expect(alert.queryAllByRole("button", { name: "Retry" })).toHaveLength(Number(status === 503));
      expect([state?.status, (state?.error as StructuredApiError).status, (state?.error as StructuredApiError).code])
        .toEqual(["error", status, code(status)]);
      // The real programme hook erases refused data; an outage retains it but the page conceals the form.
      if (status === 403) expect(state?.data).toBeUndefined();
      else expect(state?.data).toBeDefined();
    }
    expect(screen.queryByRole("form")).toBeNull();
    expect(screen.queryByText("Private application form")).toBeNull();
    expect(screen.getAllByRole("button", { name: "Retry" })).toHaveLength(Number(applicationStatus === 503) + Number(postingStatus === 503));
    expect(attempts).toEqual({ application: 2, posting: 2 });
    failed = false;
    for (const button of screen.getAllByRole("button", { name: "Retry" })) fireEvent.click(button);
    await waitFor(() => expect(attempts).toEqual({ application: applicationStatus === 503 ? 3 : 2, posting: postingStatus === 503 ? 3 : 2 }));
    await waitFor(() => expect(screen.queryByRole("button", { name: "Retry" })).toBeNull());
    expect(attempts).toEqual({ application: applicationStatus === 503 ? 3 : 2, posting: postingStatus === 503 ? 3 : 2 });
    for (const kind of ["application", "posting"] as const) {
      if ((kind === "application" ? applicationStatus : postingStatus) !== 403) continue;
      const state = client.getQueryState([...programmeKey(scope, "member"), paths[kind]]);
      expect([state?.data, (state?.error as StructuredApiError).status, (state?.error as StructuredApiError).code])
        .toEqual([undefined, 403, "permission_denied"]);
    }
    if (applicationStatus === 503 && postingStatus === 503) expect(await screen.findByRole("form")).toBeVisible();
    else expect(screen.queryByRole("form")).toBeNull();
  },
);

it.each(["account", "makerspace", "event", "application", "route", "session"] as const)(
  "discards the retained posting id when the %s identity changes", async changed => {
    const scope = { eventId: 8, makerspaceId: 3, accountId: 17 };
    const context = fixture.context as unknown as ProgrammeContext;
    const attempts = { application: 0, posting: 0 };
    let failed = false;
    vi.mocked(memberRequest).mockReset().mockImplementation(async path => {
      const kind = path.includes("/role-applications/") ? "application" : "posting";
      attempts[kind]++;
      if (failed) throw new StructuredApiError(kind === "application" ? 403 : 503, {
        code: kind === "application" ? "permission_denied" : "service_unavailable", detail: kind,
      });
      return { id: kind === "application" ? 4 : 9, event_id: 8, posting_id: 9, version: 1, state: "draft", allowed_actions: [] };
    });
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const page = (currentScope = scope, applicationId = 4, base = "/programme") =>
      <QueryClientProvider client={client}><MemoryRouter><ProgrammeRolePage scope={currentScope} context={context}
        applicationId={applicationId} base={base} /></MemoryRouter></QueryClientProvider>;
    const view = render(page());
    await screen.findByRole("form", { name: "Role application" });
    failed = true;
    await act(async () => { await client.refetchQueries(); });
    await waitFor(() => expect(screen.getAllByRole("alert")).toHaveLength(2));
    expect(attempts).toEqual({ application: 2, posting: 2 });
    const nextScope = { ...scope, ...(changed === "account" ? { accountId: 18 } : {}),
      ...(changed === "makerspace" ? { makerspaceId: 5 } : {}), ...(changed === "event" ? { eventId: 10 } : {}) };
    if (changed === "session") vi.mocked(sessionScope).mockReturnValue(["localhost", "person", "session-2"]);
    const applicationId = changed === "application" ? 5 : 4;
    view.rerender(page(nextScope, applicationId, changed === "route" ? "/other-programme" : "/programme"));
    await waitFor(() => expect(screen.getAllByRole("alert").map(alert => alert.textContent)).toEqual(["application"]));
    const state = client.getQueryState([...programmeKey(nextScope, "member"), `/role-applications/${applicationId}/`]);
    expect([state?.data, (state?.error as StructuredApiError).status, (state?.error as StructuredApiError).code])
      .toEqual([undefined, 403, "permission_denied"]);
    expect(screen.queryByRole("form")).toBeNull();
    expect(screen.queryByRole("button", { name: "Retry" })).toBeNull();
    expect(attempts).toEqual({ application: changed === "route" ? 2 : 3, posting: 2 });
    expect(client.getQueryCache().findAll().filter(query => query.queryKey.slice(-1)[0] === "/role-postings/9/")
      .reduce((count, query) => count + query.getObserversCount(), 0)).toBe(0);
  },
);
