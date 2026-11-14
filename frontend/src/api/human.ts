import { useMutation, useQueryClient } from "@tanstack/react-query";
import { client, unwrap } from "./client";
import type { components } from "./schema";
export type ManualProof = { proof_type: "case_number" | "email_message_id" | "portal_screenshot" | "carrier_tracking"; reference: string; proof_date: string; note?: string };
export type HumanAction = { kind: "validate" | "manual-takeover" } | { kind: "reject"; reason: string } | ({ kind: "manual-proof" } & ManualProof) | { kind: "resolve"; note: string } | { kind: "checklist"; step: components["schemas"]["ChecklistStepName"] };
export function useHumanAction(id: string) {
 const cache = useQueryClient();
 return useMutation({ mutationFn: async (action: HumanAction) => {
  const params = { path: { case_id: id } };
  const body = {};
  switch (action.kind) {
   case "validate": return unwrap(await client.POST("/api/cases/{case_id}/validate", { params, body }));
   case "reject": return unwrap(await client.POST("/api/cases/{case_id}/reject", { params, body: { ...body, reason: action.reason } }));
   case "manual-takeover": return unwrap(await client.POST("/api/cases/{case_id}/manual-takeover", { params, body }));
   case "manual-proof": return unwrap(await client.POST("/api/cases/{case_id}/manual-proof", { params, body: { proof_type: action.proof_type, reference: action.reference, proof_date: action.proof_date, note: action.note || undefined } }));
   case "resolve": return unwrap(await client.POST("/api/cases/{case_id}/resolve", { params, body: { note: action.note } }));
   case "checklist": return unwrap(await client.POST("/api/cases/{case_id}/checklist/{step_name}", { params: { path: { case_id: id, step_name: action.step } }, body }));
  }
 }, onSuccess: async () => { await Promise.all([["cases"], ["case", id], ["checklist", id], ["events", id], ["journal"]].map(queryKey => cache.invalidateQueries({ queryKey }))); } });
}
