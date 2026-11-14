import { act, cleanup, renderHook } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import type { ReactNode } from "react";
import { useCaseStream } from "./useCaseStream";
import { setSseEnabled } from "@/preferences";
import type { StreamEventLocal } from "./untyped";
const event = (seq: number): StreamEventLocal => ({ seq, at: "2026-01-01T12:00:00Z", actor: "system", type: "case_created", payload: {}, hash: "hash" });
class Source {
 static instances: Source[] = [];
 onopen?: () => void;
 onerror?: () => void;
 onmessage?: (message: MessageEvent<string>) => void;
 close = vi.fn();
 addEventListener = vi.fn();
 constructor(public url: string) { Source.instances.push(this); }
}
let cache: QueryClient, fetchMock: ReturnType<typeof vi.fn>;
function mount() {
 const wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={cache}>{children}</QueryClientProvider>;
 return renderHook(() => useCaseStream("demo"), { wrapper });
}
async function tick(ms = 10) { await act(async () => { await vi.advanceTimersByTimeAsync(ms); }); }
beforeEach(() => {
 vi.useFakeTimers(); localStorage.clear(); Source.instances = [];
 cache = new QueryClient({ defaultOptions: { queries: { retry: false } } });
 fetchMock = vi.fn().mockImplementation(() => Promise.resolve(Response.json([event(1)])));
 vi.stubGlobal("fetch", fetchMock); vi.stubGlobal("EventSource", Source);
});
afterEach(() => { cleanup(); cache.clear(); vi.unstubAllGlobals(); vi.useRealTimers(); });
it("polls by default every two seconds and resumes the local sequence without duplicates", async () => {
 const hook = mount(); await tick();
 expect(hook.result.current.mode).toBe("poll"); expect(Source.instances).toHaveLength(0);
 expect(hook.result.current.data?.map(e => e.seq)).toEqual([1]);
 fetchMock.mockImplementation(() => Promise.resolve(Response.json([event(1), event(2)])));
 await tick(2000);
 expect(fetchMock).toHaveBeenCalledTimes(2); expect(hook.result.current.data?.map(e => e.seq)).toEqual([1, 2]);
 await tick(2000);
 expect(hook.result.current.data?.map(e => e.seq)).toEqual([1, 2]);
});
it("uses SSE only when opted in, receives named events, and reconnects after the last sequence", async () => {
 localStorage.setItem("wp-sse-enabled", "true"); cache.setQueryData(["events", "demo"], [event(5)]);
 fetchMock.mockImplementation(() => Promise.resolve(Response.json([])));
 const hook = mount(); await tick();
 const source = Source.instances[0]; expect(source.url).toBe("/api/cases/demo/stream?after=5");
 act(() => source.onopen?.()); expect(hook.result.current.connection).toBe("open");
 expect(source.addEventListener).toHaveBeenCalledWith("case_created", expect.any(Function));
 act(() => source.onmessage?.(new MessageEvent("message", { data: JSON.stringify(event(6)) }))); await tick();
 expect(hook.result.current.data?.map(e => e.seq)).toEqual([5, 6]);
 act(() => source.onerror?.()); expect(hook.result.current.connection).toBe("error");
 await tick(1500); expect(Source.instances[1].url).toBe("/api/cases/demo/stream?after=6");
 await tick(2000); expect(fetchMock).toHaveBeenCalledTimes(1);
 hook.unmount(); expect(Source.instances[1].close).toHaveBeenCalled();
});
it("switches from SSE to polling locally and closes the connection", async () => {
 localStorage.setItem("wp-sse-enabled", "true"); const hook = mount(); await tick();
 act(() => setSseEnabled(false)); await tick();
 expect(localStorage.getItem("wp-sse-enabled")).toBe("false");
 expect(hook.result.current.mode).toBe("poll"); expect(Source.instances[0].close).toHaveBeenCalled();
 await tick(2000); expect(fetchMock).toHaveBeenCalledTimes(2);
});
it("handles empty polling history, request errors and subsequent recovery", async () => {
 fetchMock.mockImplementation(() => Promise.resolve(Response.json([]))); const hook = mount(); await tick();
 expect(hook.result.current.data).toEqual([]);
 fetchMock.mockImplementation(() => Promise.resolve(new Response("error", { status: 500 })));
 await tick(2000); expect(hook.result.current.isError).toBe(true);
 fetchMock.mockImplementation(() => Promise.resolve(Response.json([event(1)])));
 await tick(2000); expect(hook.result.current.isError).toBe(false); expect(hook.result.current.data).toHaveLength(1);
});
it("rejects malformed SSE messages without corrupting cached events", async () => {
 localStorage.setItem("wp-sse-enabled", "true"); const hook = mount(); await tick();
 act(() => Source.instances[0].onmessage?.(new MessageEvent("message", { data: "{}" })));
 expect(hook.result.current.connection).toBe("error"); expect(hook.result.current.data?.map(e => e.seq)).toEqual([1]);
});
it("fills historical gaps even when newer SSE sequences were cached first", async () => {
 localStorage.setItem("wp-sse-enabled", "true"); cache.setQueryData(["events", "demo"], [event(3)]);
 fetchMock.mockImplementation(() => Promise.resolve(Response.json([event(1), event(2), event(3)])));
 const hook = mount(); await tick();
 expect(hook.result.current.data?.map(e => e.seq)).toEqual([1, 2, 3]);
});
