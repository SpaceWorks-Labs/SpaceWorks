import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { memberRequest, StructuredApiError } from "../../../lib/api";
import { MemberCommunityArea } from "./MemberCommunityArea";
import { OwnConsentStatusCard } from "./OwnConsentStatusCard";

vi.mock("../../../lib/api", async (original) => ({ ...(await original<typeof import("../../../lib/api")>()), memberRequest: vi.fn() }));

const wrap = (node: ReactNode) => render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>{node}</QueryClientProvider>);
const status = (patch: object) => ({ applies: true, state: "pending", valid_until: null, guardian_named: true,
  guardian_must_be_present: true, may_borrow: false, may_use_machines: false, ...patch });

describe("OwnConsentStatusCard (A27)", () => {
  beforeEach(() => { vi.mocked(memberRequest).mockReset(); });

  it("tells a minor their consent is waiting for their guardian, with the space's rules", async () => {
    vi.mocked(memberRequest).mockResolvedValue(status({}));
    wrap(<OwnConsentStatusCard makerspaceId={3} />);
    expect(await screen.findByRole("heading", { name: "Your guardian consent" })).toBeVisible();
    expect(screen.getByText("Waiting for your guardian")).toBeVisible();
    expect(screen.getByText(/A guardian must be with you/)).toBeVisible();
    expect(screen.getByText("You can't borrow items here yet.")).toBeVisible();
    expect(memberRequest).toHaveBeenCalledWith("/member/makerspaces/3/my-guardian-consent");
  });

  it("shows a current consent with its end date and asks for a guardian when none is named", async () => {
    vi.mocked(memberRequest).mockResolvedValue(status({ state: "current", valid_until: "2027-01-31T00:00:00Z", may_borrow: true, may_use_machines: true, guardian_must_be_present: false }));
    wrap(<OwnConsentStatusCard makerspaceId={3} />);
    expect(await screen.findByText("Consent on file")).toBeVisible();
    expect(screen.getByText(/Valid until/)).toBeVisible();
    expect(screen.queryByRole("list")).toBeNull();
  });

  it("asks staff to add a guardian when none is on record", async () => {
    vi.mocked(memberRequest).mockResolvedValue(status({ state: "expired", guardian_named: false }));
    wrap(<OwnConsentStatusCard makerspaceId={3} />);
    expect(await screen.findByText("Consent needs renewing")).toBeVisible();
    expect(screen.getByText(/No guardian is on record yet/)).toBeVisible();
  });

  it("renders nothing for an adult or when the feature answers 404", async () => {
    vi.mocked(memberRequest).mockResolvedValueOnce(status({ applies: false, state: "not_applicable" }));
    const adult = wrap(<OwnConsentStatusCard makerspaceId={3} />);
    await waitFor(() => expect(adult.container).toBeEmptyDOMElement());
    adult.unmount();
    vi.mocked(memberRequest).mockRejectedValueOnce(new StructuredApiError(404, { detail: "Not found." }));
    const off = wrap(<OwnConsentStatusCard makerspaceId={3} />);
    await waitFor(() => expect(off.container).toBeEmptyDOMElement());
  });

  it("is only requested while membership.minors is on", () => {
    vi.mocked(memberRequest).mockResolvedValue([]);
    wrap(<MemberCommunityArea makerspaceId={3} memberBase="/member" features={[]} activeMember />);
    expect(memberRequest).not.toHaveBeenCalled();
  });
});
