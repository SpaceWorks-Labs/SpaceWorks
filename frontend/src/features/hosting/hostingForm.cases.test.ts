import { describe, expect, it } from "vitest";
import { StructuredApiError } from "../../lib/api/errors";
import { EMPTY_HOSTING_FORM, hostingErrorText, hostingFieldErrors, hostingRequestBody, type HostingFormValue } from "./hostingForm";

const filled = (over: Partial<HostingFormValue> = {}): HostingFormValue => ({ ...EMPTY_HOSTING_FORM, applicant_name: " Ann ", applicant_email: " a@x.org ",
  space_name: " Forge ", location: " Kochi ", description: " A space ", website: "", ...over });

describe("hostingRequestBody", () => {
  it("trims required fields and leaves blank optional fields out", () => expect(hostingRequestBody(filled())).toEqual({
    applicant_name: "Ann", applicant_email: "a@x.org", space_name: "Forge", location: "Kochi", description: "A space", website: "" }));
  it("sends the honeypot untouched", () => expect(hostingRequestBody(filled({ website: " bot " })).website).toBe(" bot "));
  it("includes trimmed optional fields when filled", () => expect(hostingRequestBody(filled({ applicant_phone: " 99 ", space_website_url: " https://x.org ",
    proposed_slug: " forge ", new_organization_name: " Org " }))).toMatchObject({ applicant_phone: "99", space_website_url: "https://x.org", proposed_slug: "forge", new_organization_name: "Org" }));
  it("leaves the organization name out when the caller says so", () => expect(hostingRequestBody(filled({ new_organization_name: "Org" }), { includeOrganization: false }))
    .not.toHaveProperty("new_organization_name"));
  it("marks an organization workspace and drops a blank location", () => {
    const body = hostingRequestBody(filled({ requested_kind: "organization", location: "  " }));
    expect(body.requested_kind).toBe("organization");
    expect(body).not.toHaveProperty("location");
    expect(hostingRequestBody(filled({ requested_kind: "organization" })).location).toBe("Kochi");
  });
  it("does not send a kind for a makerspace", () => expect(hostingRequestBody(filled())).not.toHaveProperty("requested_kind"));
  it.each([["12", 12], [" 7 ", 7]])("converts expected members %j to the number %s", (raw, n) => expect(hostingRequestBody(filled({ expected_members: raw })).expected_members).toBe(n));
  it.each(["", "0", "-3", "2.5", "abc"])("omits expected members %j", (raw) => expect(hostingRequestBody(filled({ expected_members: raw }))).not.toHaveProperty("expected_members"));
});

describe("hostingFieldErrors", () => {
  it("returns one first message per field, skipping detail and code", () => expect(hostingFieldErrors(new StructuredApiError(400, {
    applicant_email: ["Bad email", "Second"], space_name: "Too short", detail: "x", code: "invalid", count: [3] } as never))).toEqual({ applicant_email: "Bad email", space_name: "Too short" }));
  it("ignores non-400 errors and non-API errors", () => {
    expect(hostingFieldErrors(new StructuredApiError(500, { space_name: ["x"] } as never))).toEqual({});
    expect(hostingFieldErrors(new Error("boom"))).toEqual({});
  });
});

describe("hostingErrorText", () => {
  it("explains a rate limit", () => expect(hostingErrorText(new StructuredApiError(429, {}), "nf")).toBe("Too many requests from this connection. Please try again later."));
  it("uses the caller's not-found copy for a 404", () => expect(hostingErrorText(new StructuredApiError(404, {}), "This invite is gone.")).toBe("This invite is gone."));
  it("prefers the non-field error on a 400, then the detail, then the generic prompt", () => {
    expect(hostingErrorText(new StructuredApiError(400, { non_field_errors: ["Pick one"] } as never), "nf")).toBe("Pick one");
    expect(hostingErrorText(new StructuredApiError(400, { detail: "Detail text" }), "nf")).toBe("Detail text");
    expect(hostingErrorText(new StructuredApiError(400, { space_name: ["x"] } as never), "nf")).toBe("Check the highlighted fields and try again.");
  });
  it("passes any other status through as the error message", () => expect(hostingErrorText(new StructuredApiError(503, { detail: "Down for work" }), "nf")).toBe(new StructuredApiError(503, { detail: "Down for work" }).message));
  it("uses a plain Error's message and a generic line for anything else", () => {
    expect(hostingErrorText(new Error("offline"), "nf")).toBe("offline");
    expect(hostingErrorText("weird", "nf")).toBe("Could not send your request.");
  });
});
