import type labels from "@/i18n/en/enums.json";
export type PurchaseGuardState = keyof typeof labels.PurchaseGuardState;
export interface ChatMessage { id: string; role: "human" | "assistant"; text?: string; textKey?: string }
export interface ChatReply { message: ChatMessage; case_id?: string; equipment?: string; questions?: string[] }
export interface ChatConversation { id: string; messages: ChatMessage[] }
export interface ChatApi { startConversation(): Promise<ChatConversation>; sendMessage(conversationId: string, message: string): Promise<ChatReply> }
export interface ExpiringRight { equipment: string; right: keyof typeof labels.RightType; endsAt: string }
export interface ScanSummary { company: string; invoices: number; coveredEquipmentEur: number; possibleSavingsEur: number; realizedSavingsEur: number; expiring: ExpiringRight[] }
export interface ScanApi { scan(onProgress?: (percent: number) => void): Promise<ScanSummary> }
export interface PurchaseRecommendation { id: string; company: string; equipment: string; amountEur: number; state: PurchaseGuardState; reason?: string; cancelledAt?: string; resolvedAt?: string }
export interface PurchaseGuardApi {
 recommendations(): Promise<PurchaseRecommendation[]>;
 decide(item: PurchaseRecommendation, choice: "suspend" | "keep", reason?: string): Promise<PurchaseRecommendation>;
 confirmCancellation(item: PurchaseRecommendation): Promise<PurchaseRecommendation>;
 resolveCase(item: PurchaseRecommendation): Promise<PurchaseRecommendation>;
}
const latency = () => new Promise<void>(resolve => setTimeout(resolve, 150));
export class MockChatApi implements ChatApi {
 async startConversation(): Promise<ChatConversation> { await latency(); return { id: crypto.randomUUID(), messages: [{ id: crypto.randomUUID(), role: "assistant", textKey: "greeting" }] }; }
 async sendMessage(conversationId: string, message: string): Promise<ChatReply> {
  await latency();
  if (!conversationId || !message.trim()) throw new Error("Message and conversation are required");
  return { message: { id: crypto.randomUUID(), role: "assistant", textKey: "mockReply" }, case_id: "appelia-simulated-case", equipment: "Jabra Evolve2 65", questions: ["clarification"] };
 }
}
export class MockScanApi implements ScanApi {
 async scan(onProgress?: (percent: number) => void): Promise<ScanSummary> {
  for (const percent of [0, 25, 60, 100]) { await latency(); onProgress?.(percent); }
  return { company: "Appelia", invoices: 60, coveredEquipmentEur: 1399, possibleSavingsEur: 199, realizedSavingsEur: 0, expiring: [{ equipment: "Jabra Evolve2 65", right: "manufacturer_warranty", endsAt: new Date(Date.now() + 21 * 86400000).toISOString() }] };
 }
}
function saving(item: PurchaseRecommendation): PurchaseRecommendation { return { ...item, state: item.cancelledAt && item.resolvedAt ? "saving_realized" : item.state }; }
export class MockPurchaseGuardApi implements PurchaseGuardApi {
 async recommendations(): Promise<PurchaseRecommendation[]> { await latency(); return [{ id: "appelia-demo-1", company: "Appelia", equipment: "Jabra Evolve2 65", amountEur: 120, state: "recommendation" }]; }
 async decide(item: PurchaseRecommendation, choice: "suspend" | "keep", reason?: string): Promise<PurchaseRecommendation> {
  await latency();
  if (item.state !== "awaiting_decision" || (choice === "keep" && !reason?.trim())) throw new Error("Decision and reason required");
  return { ...item, reason: reason?.trim(), state: choice === "suspend" ? "purchase_suspended" : "purchase_kept" };
 }
 async confirmCancellation(item: PurchaseRecommendation) { await latency(); if (item.state !== "purchase_suspended") throw new Error("Purchase is not suspended"); return saving({ ...item, cancelledAt: new Date().toISOString() }); }
 async resolveCase(item: PurchaseRecommendation) { await latency(); if (item.state !== "purchase_suspended") throw new Error("Purchase is not suspended"); return saving({ ...item, resolvedAt: new Date().toISOString() }); }
}
