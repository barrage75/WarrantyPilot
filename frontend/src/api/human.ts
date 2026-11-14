import { useMutation, useQueryClient } from "@tanstack/react-query";
import { client, unwrap } from "./client";
import type { components } from "./schema";
export type HumanAction = { kind: "validate" | "manual-takeover"; person_id: string } | { kind: "reject"; person_id: string; reason: string } | { kind: "manual-proof"; person_id: string; proof: string } | { kind: "checklist"; person_id: string; step: components["schemas"]["ChecklistStepName"] };
export function useHumanAction(id: string) {
 const cache = useQueryClient();
 return useMutation({ mutationFn: async (action: HumanAction) => {
  const params = { path: { case_id: id } };
  const body = { person_id: action.person_id };
  switch (action.kind) {
   case "validate": return unwrap(await client.POST("/api/cases/{case_id}/validate", { params, body }));
   case "reject": return unwrap(await client.POST("/api/cases/{case_id}/reject", { params, body: { ...body, reason: action.reason } }));
   case "manual-takeover": return unwrap(await client.POST("/api/cases/{case_id}/manual-takeover", { params, body }));
   case "manual-proof": return unwrap(await client.POST("/api/cases/{case_id}/manual-proof", { params, body: { ...body, proof: action.proof } }));
   case "checklist": return unwrap(await client.POST("/api/cases/{case_id}/checklist/{step_name}", { params: { path: { case_id: id, step_name: action.step } }, body }));
  }
 }, onSuccess: async () => { await Promise.all([["cases"], ["case", id], ["checklist", id], ["events", id], ["journal"]].map(queryKey => cache.invalidateQueries({ queryKey }))); } });
}
