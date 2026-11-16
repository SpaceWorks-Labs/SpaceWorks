// A tiny OpenAPI document for the API reference tests: two grouped tags, an undeclared tag, a
// self-referencing schema (cycle), an unreachable schema and the x- hints the real schema carries.
export const fixtureSpec = {
  openapi: "3.0.3",
  info: { title: "Space Works API", version: "9.9.9" },
  tags: [{ name: "Loans", description: "Borrowing and returns." }],
  "x-tagGroups": [{ name: "Inventory and loans", tags: ["Loans", "Stock"] }],
  components: {
    securitySchemes: {
      jwtAuth: { type: "http", scheme: "bearer", description: "A signed-in staff session." },
      PublishableKey: { type: "apiKey", in: "header", name: "X-Publishable-Key", description: "A public client key." },
    },
    schemas: {
      Loan: {
        type: "object", required: ["item", "status"],
        properties: {
          id: { type: "integer", readOnly: true },
          item: { $ref: "#/components/schemas/Item" },
          status: { type: "string", enum: ["requested", "issued", "returned"] },
          note: { type: "string", nullable: true, description: "What the borrower said.", example: "Chuck sticks" },
        },
      },
      Item: { type: "object", properties: { name: { type: "string" }, parts: { type: "array", items: { $ref: "#/components/schemas/Item" } } } },
      LoanRequest: { type: "object", required: ["item_id"], properties: { item_id: { type: "integer" }, note: { type: "string" } } },
      Problem: { type: "object", properties: { detail: { type: "string" } }, examples: { huge: { value: "x" } } },
      Unused: { type: "object", properties: { secret: { type: "string" } } },
    },
  },
  paths: {
    "/api/v1/admin/makerspaces/{makerspace_id}/loans/": {
      post: {
        operationId: "loans_create", summary: "Create a loan", tags: ["Loans"],
        description: "Records a loan.\n\nRequires the issue_request action.",
        security: [{ jwtAuth: [] }],
        parameters: [
          { in: "path", name: "makerspace_id", required: true, schema: { type: "integer" } },
          { in: "query", name: "dry_run", required: true, schema: { type: "boolean" }, description: "Validate only." },
        ],
        requestBody: { required: true, content: { "application/json": { schema: { $ref: "#/components/schemas/LoanRequest" } } } },
        responses: {
          "201": { description: "Created.", content: { "application/json": { schema: { $ref: "#/components/schemas/Loan" } } } },
          "403": { description: "Not allowed.", content: { "application/json": { schema: { $ref: "#/components/schemas/Problem" } } } },
        },
      },
    },
    "/api/public/{slug}/loans/": {
      get: {
        operationId: "public_loans_list", summary: "List public loans", tags: ["Loans"],
        security: [{ PublishableKey: [] }, {}],
        parameters: [{ in: "path", name: "slug", required: true, schema: { type: "string" } }],
        responses: { "200": { description: "", content: { "application/json": { schema: { type: "array", items: { $ref: "#/components/schemas/Loan" } } } } } },
      },
    },
    "/api/v1/stock/": {
      delete: { operationId: "stock_clear", summary: "Clear stock", tags: ["Stock"], "x-request-body": "none", "x-response-body": "none", responses: { "204": { description: "Cleared." } } },
    },
    "/api/v1/hooks/": {
      post: { operationId: "hook_receive", summary: "Receive a hook", tags: ["Webhooks"], "x-free-form": { request: "The provider's callback." }, responses: { "200": { description: "Acknowledged." } } },
    },
  },
};
