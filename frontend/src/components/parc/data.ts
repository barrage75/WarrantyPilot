import { useQuery } from "@tanstack/react-query";
import { client, unwrap } from "@/api/client";
import type { components } from "@/api/schema";

export type FleetEquipment = components["schemas"]["EquipmentWarrantyOverview"];
export type Coverage = components["schemas"]["Coverage"];
export type Verdict = components["schemas"]["VerdictValue"];
export function countByVerdict(items: readonly Pick<FleetEquipment, "verdict">[]): Record<Verdict, number> {
 const counts: Record<Verdict, number> = { covered: 0, likely_covered: 0, to_verify: 0, not_covered: 0, out_of_manufacturer: 0 };
 for (const item of items) counts[item.verdict] += 1;
 return counts;
}
export function useOverview(coverage?: Coverage, q?: string) {
 return useQuery({ queryKey: ["equipment-overview", coverage ?? "", q ?? ""], queryFn: async ({ signal }) => unwrap(await client.GET("/api/equipment/overview", { params: { query: { coverage, q: q || undefined } }, signal })), staleTime: 15_000 });
}
export function useSavings() {
 return useQuery({ queryKey: ["savings"], queryFn: async () => unwrap(await client.GET("/api/reports/savings")), staleTime: 15_000 });
}
