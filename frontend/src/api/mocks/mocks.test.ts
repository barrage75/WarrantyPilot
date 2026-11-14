import { afterEach, expect, it, vi } from "vitest";
import { MockChatApi, MockPurchaseGuardApi, MockScanApi } from "./index";
afterEach(() => vi.useRealTimers());
it("returns fictional Appelia data, progress, and zero realized savings without fetch", async () => {
 vi.useFakeTimers();
 const fetch = vi.spyOn(globalThis, "fetch"), progress = vi.fn(), api = new MockChatApi();
 const chat = api.startConversation(), scan = new MockScanApi().scan(progress), guard = new MockPurchaseGuardApi().recommendations();
 await vi.runAllTimersAsync();
 expect(await scan).toMatchObject({ company: "Appelia", realizedSavingsEur: 0, coveredEquipmentEur: 1399 });
 expect(progress.mock.calls.map(([value]) => value)).toEqual([0, 25, 60, 100]);
 expect((await guard)[0].state).toBe("recommendation");
 const conversation = await chat;
 expect(conversation.messages).toHaveLength(1);
 const reply = api.sendMessage(conversation.id, "Casque en panne");
 await vi.runAllTimersAsync();
 expect(await reply).toMatchObject({ case_id: "appelia-simulated-case", equipment: "Jabra Evolve2 65" });
 expect(fetch).not.toHaveBeenCalled(); fetch.mockRestore();
});
it("rejects empty chat input", async () => {
 vi.useFakeTimers();
 const result = expect(new MockChatApi().sendMessage("demo", " ")).rejects.toThrow("Message and conversation are required");
 await vi.runAllTimersAsync(); await result;
});
it("requires both cancellation and resolution before counting savings in either order", async () => {
 vi.useFakeTimers(); const api = new MockPurchaseGuardApi();
 for (const reverse of [false, true]) {
  const initial = api.recommendations(); await vi.runAllTimersAsync();
  const decision = api.decide({ ...(await initial)[0], state: "awaiting_decision" }, "suspend"); await vi.runAllTimersAsync();
  const first = reverse ? api.resolveCase(await decision) : api.confirmCancellation(await decision); await vi.runAllTimersAsync();
  expect((await first).state).toBe("purchase_suspended");
  const second = reverse ? api.confirmCancellation(await first) : api.resolveCase(await first); await vi.runAllTimersAsync();
  expect(await second).toMatchObject({ state: "saving_realized", cancelledAt: expect.any(String), resolvedAt: expect.any(String) });
 }
});
it("rejects keeping a purchase without a reason and invalid state transitions", async () => {
 vi.useFakeTimers(); const api = new MockPurchaseGuardApi();
 const initial = api.recommendations(); await vi.runAllTimersAsync(); const item = (await initial)[0];
 const reason = expect(api.decide({ ...item, state: "awaiting_decision" }, "keep", " ")).rejects.toThrow("Decision and reason required");
 const cancellation = expect(api.confirmCancellation(item)).rejects.toThrow("Purchase is not suspended");
 await vi.runAllTimersAsync(); await Promise.all([reason, cancellation]);
});
