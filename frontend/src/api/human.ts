import { useMutation, useQueryClient } from "@tanstack/react-query";
import { client, unwrap } from "./client";
import type { components } from "./schema";
<<<<<<< HEAD
export type HumanAction = { kind: "validate" | "manual-takeover"; person_id: string } | { kind: "reject"; person_id: string; reason: string } | { kind: "manual-proof"; person_id: string; proof: string } | { kind: "resolve"; person_id: string; note: string } | { kind: "checklist"; person_id: string; step: components["schemas"]["ChecklistStepName"] };
||||||| parent of 13ec235 (feat(securite): écran de connexion, session frontend, e2e authentifiés et ancrage non bloquant)
export type HumanAction = { kind: "validate" | "manual-takeover"; person_id: string } | { kind: "reject"; person_id: string; reason: string } | { kind: "manual-proof"; person_id: string; proof: string } | { kind: "checklist"; person_id: string; step: components["schemas"]["ChecklistStepName"] };
=======
export type ManualProof = { proof_type: "case_number" | "email_message_id" | "portal_screenshot" | "carrier_tracking"; reference: string; proof_date: string; note?: string };
export type HumanAction = { kind: "validate" | "manual-takeover" } | { kind: "reject"; reason: string } | ({ kind: "manual-proof" } & ManualProof) | { kind: "checklist"; step: components["schemas"]["ChecklistStepName"] };
>>>>>>> 13ec235 (feat(securite): écran de connexion, session frontend, e2e authentifiés et ancrage non bloquant)
export function useHumanAction(id: string) {
 const cache = useQueryClient();
 return useMutation({ mutationFn: async (action: HumanAction) => {
  const params = { path: { case_id: id } };
  const body = {};
  switch (action.kind) {
   case "validate": return unwrap(await client.POST("/api/cases/{case_id}/validate", { params, body }));
   case "reject": return unwrap(await client.POST("/api/cases/{case_id}/reject", { params, body: { ...body, reason: action.reason } }));
   case "manual-takeover": return unwrap(await client.POST("/api/cases/{case_id}/manual-takeover", { params, body }));
<<<<<<< HEAD
   case "manual-proof": return unwrap(await client.POST("/api/cases/{case_id}/manual-proof", { params, body: { ...body, proof: action.proof } }));
   case "resolve": return unwrap(await client.POST("/api/cases/{case_id}/resolve", { params, body: { ...body, note: action.note } }));
||||||| parent of 13ec235 (feat(securite): écran de connexion, session frontend, e2e authentifiés et ancrage non bloquant)
   case "manual-proof": return unwrap(await client.POST("/api/cases/{case_id}/manual-proof", { params, body: { ...body, proof: action.proof } }));
=======
   case "manual-proof": return unwrap(await client.POST("/api/cases/{case_id}/manual-proof", { params, body: { proof_type: action.proof_type, reference: action.reference, proof_date: action.proof_date, note: action.note || undefined } }));
>>>>>>> 13ec235 (feat(securite): écran de connexion, session frontend, e2e authentifiés et ancrage non bloquant)
   case "checklist": return unwrap(await client.POST("/api/cases/{case_id}/checklist/{step_name}", { params: { path: { case_id: id, step_name: action.step } }, body }));
  }
 }, onSuccess: async () => { await Promise.all([["cases"], ["case", id], ["checklist", id], ["events", id], ["journal"]].map(queryKey => cache.invalidateQueries({ queryKey }))); } });
}
