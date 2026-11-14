import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { cancelValidation, isValidationPending, queueValidation, VALIDATION_DELAY_MS } from "@/lib/pendingValidation";

beforeEach(() => vi.useFakeTimers());
afterEach(() => { window.dispatchEvent(new Event("pagehide")); vi.useRealTimers(); });
it("cancels without sending a request", async () => {
 const send = vi.fn().mockResolvedValue(undefined);
 queueValidation("cancel", send, vi.fn());
 await vi.advanceTimersByTimeAsync(4000);
 expect(send).not.toHaveBeenCalled();
 expect(cancelValidation("cancel")).toBe(true);
 await vi.advanceTimersByTimeAsync(VALIDATION_DELAY_MS);
 expect(send).not.toHaveBeenCalled();
 expect(isValidationPending("cancel")).toBe(false);
});
it("sends exactly once after five seconds, never before", async () => {
 const send = vi.fn().mockResolvedValue(undefined);
 queueValidation("elapsed", send, vi.fn());
 await vi.advanceTimersByTimeAsync(4999);
 expect(send).not.toHaveBeenCalled();
 await vi.advanceTimersByTimeAsync(1);
 expect(send).toHaveBeenCalledTimes(1);
 await vi.advanceTimersByTimeAsync(10000);
 expect(send).toHaveBeenCalledTimes(1);
 expect(isValidationPending("elapsed")).toBe(false);
});
it("deduplicates double clicks and keeps the lock during the request", async () => {
 let finish!: () => void;
 const send = vi.fn(() => new Promise<void>(resolve => { finish = resolve; }));
 expect(queueValidation("double", send, vi.fn())).toBe(true);
 expect(queueValidation("double", send, vi.fn())).toBe(false);
 await vi.advanceTimersByTimeAsync(VALIDATION_DELAY_MS);
 expect(queueValidation("double", send, vi.fn())).toBe(false);
 expect(cancelValidation("double")).toBe(false);
 expect(send).toHaveBeenCalledTimes(1);
 finish();
 await vi.advanceTimersByTimeAsync(0);
 expect(isValidationPending("double")).toBe(false);
});
it("drops unsent approvals when the tab closes", async () => {
 const send = vi.fn().mockResolvedValue(undefined);
 queueValidation("closing", send, vi.fn());
 window.dispatchEvent(new Event("pagehide"));
 await vi.advanceTimersByTimeAsync(VALIDATION_DELAY_MS);
 expect(send).not.toHaveBeenCalled();
});
it("reports errors and releases the queue for an explicit retry", async () => {
 const error = new Error("offline"), onError = vi.fn();
 queueValidation("error", vi.fn().mockRejectedValue(error), onError);
 await vi.advanceTimersByTimeAsync(VALIDATION_DELAY_MS);
 expect(onError).toHaveBeenCalledWith(error);
 expect(isValidationPending("error")).toBe(false);
});
