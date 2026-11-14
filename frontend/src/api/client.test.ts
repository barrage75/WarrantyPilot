import { afterEach, expect, it, vi } from "vitest";
import { localRequest, unwrap } from "./client";
afterEach(() => vi.unstubAllGlobals());
it("unwraps a typed response", async () => expect(await unwrap({ data: [], response: new Response("[]") })).toEqual([]));
it("rejects API errors", async () => expect(unwrap({ error: "missing", response: new Response("", { status: 404 }) })).rejects.toMatchObject({ status: 404 }));
it("fetches local contracts", async () => { vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response('{"paused":false}'))); expect(await localRequest("/agent/status")).toEqual({ paused: false }); });
it("reports local failure", async () => { vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("failed", { status: 500 }))); await expect(localRequest("/agent/status")).rejects.toMatchObject({ status: 500 }); });
