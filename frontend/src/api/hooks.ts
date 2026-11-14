import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { client, localRequest, unwrap } from "./client";
import type { components } from "./schema";
import type { MethodResponse } from "openapi-fetch";
import type { AgentStatusLocal, JournalVerifyLocal, JournalAnchorLocal, PreflightLocal, ResetLocal } from "./untyped";
export const useCases = () => useQuery<MethodResponse<typeof client, "get", "/api/cases">>({ queryKey: ["cases"], queryFn: async () => unwrap(await client.GET("/api/cases")) });
export const useCase = (id: string) => useQuery<MethodResponse<typeof client, "get", "/api/cases/{case_id}">>({ queryKey: ["case", id], queryFn: async () => unwrap(await client.GET("/api/cases/{case_id}", { params: { path: { case_id: id } } })), enabled: !!id });
export const useChecklist = (id: string) => useQuery({ queryKey: ["checklist", id], queryFn: async () => unwrap(await client.GET("/api/cases/{case_id}/checklist", { params: { path: { case_id: id } } })), enabled: !!id, retry: false });
export const useSettings = () => useQuery({ queryKey: ["settings"], queryFn: async () => unwrap(await client.GET("/api/settings")) });
export function useUpdateSettings() {
 const cache = useQueryClient();
 return useMutation({ mutationFn: async (body: components["schemas"]["Settings-Input"]) => unwrap(await client.PUT("/api/settings", { body })), onSuccess: () => { void cache.invalidateQueries({ queryKey: ["settings"] }); void cache.invalidateQueries({ queryKey: ["agent"] }); } });
}
export const useAgentStatus = () => useQuery({ queryKey: ["agent"], queryFn: () => localRequest<AgentStatusLocal>("/agent/status"), refetchInterval: 5000 });
export function useToggleAgent() {
 const cache = useQueryClient();
 return useMutation({ mutationFn: (paused: boolean) => localRequest<AgentStatusLocal>(paused ? "/agent/resume" : "/agent/pause", "POST"), onSuccess: (data) => { cache.setQueryData(["agent"], data); void cache.invalidateQueries({ queryKey: ["journal"] }); } });
}
export const useJournal = () => useQuery({ queryKey: ["journal"], queryFn: () => localRequest<JournalVerifyLocal>("/journal/verify"), refetchInterval: 10000 });
export const usePreflight = () => useQuery({ queryKey: ["preflight"], queryFn: () => localRequest<PreflightLocal>("/demo/preflight") });
export function useResetDemo() {
 const cache = useQueryClient();
 return useMutation({ mutationFn: () => localRequest<ResetLocal>("/demo/reset", "POST", { confirm: "RESET" }), onSuccess: async () => { await cache.cancelQueries(); cache.removeQueries({ queryKey: ["events"] }); await cache.invalidateQueries(); } });
}
export function useAnchorJournal() {
 const cache = useQueryClient();
 return useMutation({ mutationFn: () => localRequest<JournalAnchorLocal>("/journal/anchor", "POST"), onSuccess: () => { void cache.invalidateQueries({ queryKey: ["journal"] }); void cache.invalidateQueries({ queryKey: ["preflight"] }); } });
}
