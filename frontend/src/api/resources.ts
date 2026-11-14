import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { client, unwrap } from "./client";
import type { components } from "./schema";
export type Person = components["schemas"]["Person"];
export type Equipment = components["schemas"]["Equipment"];
export type ChatConversation = components["schemas"]["ChatConversation"];
export type ChatReply = components["schemas"]["ChatReply"];
export type ScanSummary = components["schemas"]["ScanSummary"];
export type PurchaseRecommendation = components["schemas"]["PurchaseRecommendation"];
export type CaseActionHistory = components["schemas"]["CaseActionHistory"];
export const usePeople = () => useQuery({ queryKey: ["people"], queryFn: async () => unwrap(await client.GET("/api/people")), staleTime: 60000 });
export const useEquipment = () => useQuery({ queryKey: ["equipment"], queryFn: async () => unwrap(await client.GET("/api/equipment")), staleTime: 60000 });
export const equipmentLabel = (item?: Equipment) => item ? `${item.brand} ${item.model} · ${item.serial}` : undefined;
export const useCaseActions = (id: string) => useQuery({ queryKey: ["actions", id], queryFn: async () => unwrap(await client.GET("/api/cases/{case_id}/actions", { params: { path: { case_id: id } } })), enabled: !!id, refetchInterval: 2000 });
export const startConversation = async () => unwrap(await client.POST("/api/chat/conversations"));
export const sendChatMessage = async (conversationId: string, text: string, reporterId: string) => unwrap(await client.POST("/api/chat/conversations/{conversation_id}/messages", { params: { path: { conversation_id: conversationId } }, body: { text, reporter_id: reporterId } }));
export const startScan = async () => unwrap(await client.POST("/api/scan"));
export const useScan = (scanId?: string) => useQuery({ queryKey: ["scan", scanId], queryFn: async () => unwrap(await client.GET("/api/scan/{scan_id}", { params: { path: { scan_id: scanId! } } })), enabled: !!scanId, refetchInterval: query => query.state.data?.status === "running" || !query.state.data ? 500 : false });
export const usePurchaseRequests = () => useQuery({ queryKey: ["purchase-requests"], queryFn: async () => unwrap(await client.GET("/api/purchase-requests")) });
export type PurchaseAction = { kind: "decide"; choice: "suspend" | "keep"; reason?: string } | { kind: "confirm-cancellation" } | { kind: "resolve-case" };
export function usePurchaseAction(id: string) {
 const cache = useQueryClient();
 return useMutation({ mutationFn: async (action: PurchaseAction) => {
  const params = { path: { purchase_id: id } };
  switch (action.kind) {
   case "decide": return unwrap(await client.POST("/api/purchase-requests/{purchase_id}/decision", { params, body: { choice: action.choice, reason: action.reason ?? null } }));
   case "confirm-cancellation": return unwrap(await client.POST("/api/purchase-requests/{purchase_id}/confirm-cancellation", { params, body: {} }));
   case "resolve-case": return unwrap(await client.POST("/api/purchase-requests/{purchase_id}/resolve-case", { params }));
  }
 }, onSuccess: updated => { cache.setQueryData<PurchaseRecommendation[]>(["purchase-requests"], old => old?.map(item => item.id === updated.id ? updated : item)); void cache.invalidateQueries({ queryKey: ["cases"] }); void cache.invalidateQueries({ queryKey: ["journal"] }); } });
}
