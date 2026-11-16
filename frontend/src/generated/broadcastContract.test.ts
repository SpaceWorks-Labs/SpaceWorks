import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { URL as NodeURL } from "node:url";
import type { BroadcastInput, Broadcast, EventBroadcastInput, EventBroadcast } from "./api";

type JsonSchema = unknown;
type ResponseSchema = { content: { "application/json": { schema: JsonSchema } } };
type Operation = { requestBody: ResponseSchema; responses: Record<string, ResponseSchema> };
type ContractSchema = {
  components: { schemas: {
    BroadcastInput: { required: string[]; properties: Record<string, unknown> & { body: { maxLength: number } } };
    Broadcast: { properties: Record<string, unknown> };
    BroadcastResult: { properties: { broadcast: JsonSchema } };
    EventBroadcastInput: { required: string[] };
    EventBroadcast: { properties: Record<string, unknown> };
    EventBroadcastList: { properties: { results: { items: JsonSchema } } };
  } };
  paths: {
    "/api/v1/notifications/broadcasts/{makerspace_id}": { post: Operation };
    "/api/v1/admin/events/{id}/broadcasts/": { post: Operation; get: Operation };
    "/api/v1/admin/events/{id}/broadcasts/{campaign_id}/queue/": { post: Operation };
    "/api/v1/admin/events/{id}/broadcasts/{campaign_id}/cancel/": { post: Operation };
  };
};
const schema = JSON.parse(readFileSync(new NodeURL("../../openapi-schema.json", import.meta.url), "utf8")) as ContractSchema;
const components = schema.components.schemas;
const ref = (name: string) => ({ $ref: `#/components/schemas/${name}` });

describe("broadcast API contracts", () => {
  it("preserves notification title, segmentation and response fields", () => {
    const input: BroadcastInput = { title: "Announcement", body: "Hello", plan_id: 1, status: "active", machine_type_id: 2 };
    const output: Broadcast = { id: 1, title: input.title, body: input.body, created_at: "2026-10-15T00:00:00Z" };
    expect(components.BroadcastInput.required).toEqual(["body", "title"]);
    expect(Object.keys(components.BroadcastInput.properties).sort()).toEqual(Object.keys(input).sort());
    expect(components.BroadcastInput.properties.body.maxLength).toBe(12000);
    expect(Object.keys(components.Broadcast.properties).sort()).toEqual(Object.keys(output).sort());
    const post = schema.paths["/api/v1/notifications/broadcasts/{makerspace_id}"].post;
    expect(post.requestBody.content["application/json"].schema).toEqual(ref("BroadcastInput"));
    expect(post.responses["201"].content["application/json"].schema).toEqual(ref("BroadcastResult"));
    expect(components.BroadcastResult.properties.broadcast).toEqual(ref("Broadcast"));
  });

  it("uses event components for list, compose, queue and cancel", () => {
    const input: EventBroadcastInput = { subject: "Workshop", body: "Hello" };
    const output: EventBroadcast = {
      id: 1, event: 2, subject: input.subject, body: input.body, statuses: ["registered"],
      attendance: "any", status: "draft", created_at: "2026-10-15T00:00:00Z", queued_at: null, completed_at: null,
      version: 1, render_schema_version: 1, design: "classic", ctas: [], available_at: null, undo_hold: false,
    };
    expect(components.EventBroadcastInput.required).toEqual(["body", "subject"]);
    expect(Object.keys(components.EventBroadcast.properties).sort()).toEqual(Object.keys(output).sort());
    const routes = schema.paths;
    const list = routes["/api/v1/admin/events/{id}/broadcasts/"];
    expect(list.post.requestBody.content["application/json"].schema).toEqual(ref("EventBroadcastInput"));
    expect(list.post.responses["201"].content["application/json"].schema).toEqual(ref("EventBroadcast"));
    expect(list.get.responses["200"].content["application/json"].schema).toEqual(ref("EventBroadcastList"));
    expect(components.EventBroadcastList.properties.results.items).toEqual(ref("EventBroadcast"));
    for (const path of [
      "/api/v1/admin/events/{id}/broadcasts/{campaign_id}/queue/",
      "/api/v1/admin/events/{id}/broadcasts/{campaign_id}/cancel/",
    ] as const) {
      expect(routes[path].post.responses["200"].content["application/json"].schema).toEqual(ref("EventBroadcast"));
    }
  });
});
