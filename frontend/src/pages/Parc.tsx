import { useDeferredValue, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { motion, useReducedMotion } from "motion/react";
import { Search, ChevronLeft, ChevronRight } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Tile } from "@/components/bento/Tile";
import { EquipmentIcon } from "@/components/bento/EquipmentIcon";
import { WarrantyRing } from "@/components/bento/WarrantyRing";
import { EmptyState } from "@/components/bento/EmptyState";
import { StatusDot } from "@/components/bento/StatusDot";
import { Button } from "@/components/ui/button";
import { FleetSummary } from "@/components/parc/FleetSummary";
import { EquipmentSheet } from "@/components/parc/EquipmentSheet";
import { useOverview, type Coverage, type FleetEquipment } from "@/components/parc/data";

const coverages = ["active", "expiring_soon", "expired", "leased", "unknown"] as const;
const pageSize = 24;
export default function Parc() {
 const { t } = useTranslation("parc"), reduced = useReducedMotion();
 const [params, setParams] = useSearchParams();
 const paramsRef = useRef(params);
 paramsRef.current = params;
 const search = params.get("q") ?? "";
 const [page, setPage] = useState(0), [selected, setSelected] = useState<FleetEquipment | null>(null);
 const trigger = useRef<HTMLButtonElement | null>(null);
 const coverage = coverages.includes(params.get("coverage") as Coverage) ? params.get("coverage") as Coverage : undefined;
 const deferred = useDeferredValue(search), query = useOverview(coverage, deferred);
 const items = query.data ?? [], pages = Math.max(1, Math.ceil(items.length / pageSize)), current = Math.min(page, pages - 1);
 const visible = items.slice(current * pageSize, (current + 1) * pageSize);
 function changeQuery(key: string, value?: string) { const next = new URLSearchParams(paramsRef.current); if (value) next.set(key, value); else next.delete(key); paramsRef.current = next; setParams(next, { replace: key === "q" }); setPage(0); }
 function filter(value?: Coverage) { changeQuery("coverage", value); }
 return <div className="space-y-6">
  <header className="flex flex-wrap items-end justify-between gap-5"><h1 className="max-w-xl text-4xl font-bold tracking-tight">{t("heading")}</h1><FleetSummary/></header>
  <div className="flex flex-wrap items-center justify-between gap-4"><div role="group" aria-label={t("filter")} className="flex flex-wrap gap-2">{([undefined, ...coverages] as const).map(value => <button key={value ?? "all"} type="button" aria-pressed={coverage === value} onClick={() => filter(value)} className={`min-h-10 rounded-full px-4 py-2 text-sm font-medium ${coverage === value ? "bg-ink text-white" : "bg-surface text-ink hover:bg-line"}`}>{t(value ? `coverage.${value}` : "all")}</button>)}</div><label className="flex min-h-11 w-full items-center gap-2 rounded-full bg-surface px-4 focus-within:ring-2 focus-within:ring-accent sm:w-72"><Search size={18} className="shrink-0 text-muted"/><input type="search" aria-label={t("search")} placeholder={t("search")} value={search} onChange={event => changeQuery("q", event.target.value)} className="min-w-0 flex-1 bg-transparent py-3 text-sm outline-none focus-visible:outline-none"/></label></div>
  {query.isPending && <p role="status">{t("common:loading")}</p>}
  {query.isError && <div role="alert" className="rounded-[28px] bg-surface p-6"><p className="mb-3 text-red-800">{t("error")}</p><Button onClick={() => void query.refetch()}>{t("common:refresh")}</Button></div>}
  {!query.isPending && !query.isError && !items.length && <Tile><EmptyState title={t("empty")} description={t("emptyHelp")}/></Tile>}
  <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4" aria-busy={query.isFetching}>
   {visible.map((item, index) => <motion.div key={item.equipment_id} initial={reduced ? false : { opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: reduced ? 0 : index * 0.04, duration: reduced ? 0 : 0.2 }} layoutId={reduced ? undefined : `equipment-${item.equipment_id}`} className={item.open_case_id ? "md:col-span-2" : ""}>
    <Tile highlight={!!item.open_case_id} className="h-full p-0"><button type="button" data-testid="equipment-tile" aria-haspopup="dialog" className="flex min-h-52 w-full flex-col justify-between rounded-[28px] p-6 text-left" onClick={event => { trigger.current = event.currentTarget; setSelected(item); }}><span className="mb-5 flex w-full items-start justify-between gap-4"><EquipmentIcon category={item.category}/><WarrantyRing daysLeft={item.days_left} coverage={item.coverage}/></span><span className="block w-full"><span className="block text-lg font-semibold tracking-tight">{item.label}</span><span className="mt-1 block text-sm text-muted">{item.assigned_to?.name ?? t("unassigned")}</span><span className="mt-3 flex items-center gap-2 text-sm text-muted"><StatusDot tone={item.open_case_id ? "active" : item.coverage === "active" ? "ok" : item.coverage === "expiring_soon" ? "waiting" : "idle"}/>{t(item.open_case_id ? "caseInProgress" : `coverage.${item.coverage}`)}</span></span></button></Tile>
   </motion.div>)}
  </div>
  {items.length > 0 && <nav aria-label={t("pagination")} className="flex flex-wrap items-center justify-center gap-4"><Button variant="outline" disabled={current === 0} aria-label={t("previous")} onClick={() => setPage(current - 1)}><ChevronLeft size={18}/></Button><span role="status" className="text-sm text-muted">{t("page", { page: current + 1, pages, count: items.length })}</span><Button variant="outline" disabled={current + 1 >= pages} aria-label={t("next")} onClick={() => setPage(current + 1)}><ChevronRight size={18}/></Button></nav>}
  <EquipmentSheet item={selected} onClose={() => setSelected(null)} returnFocus={() => trigger.current?.focus()}/>
 </div>;
}
