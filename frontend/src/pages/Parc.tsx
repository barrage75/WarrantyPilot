import { useDeferredValue, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Search, ChevronLeft, ChevronRight } from "lucide-react";
import { useTranslation } from "react-i18next";
import type { components } from "@/api/schema";
import { Tile } from "@/components/bento/Tile";
import { EquipmentIcon } from "@/components/bento/EquipmentIcon";
import { EmptyState } from "@/components/bento/EmptyState";
import { Button } from "@/components/ui/button";
import { FleetSummary } from "@/components/parc/FleetSummary";
import { FleetDistribution } from "@/components/parc/FleetDistribution";
import { EquipmentSheet } from "@/components/parc/EquipmentSheet";
import { useOverview, type Coverage, type FleetEquipment } from "@/components/parc/data";
import { VerdictBadge } from "@/components/Badges";
import { Pill } from "@/components/bento/Pill";

const coverages = ["active", "expiring_soon", "expired", "leased", "unknown"] as const;
const verdicts = ["covered", "likely_covered", "to_verify", "not_covered", "out_of_manufacturer"] as const;
type Verdict = components["schemas"]["VerdictValue"];
const pageSize = 24;
export default function Parc() {
 const { t, i18n } = useTranslation(["parc", "enums"]);
 const [params, setParams] = useSearchParams();
 const paramsRef = useRef(params);
 paramsRef.current = params;
 const search = params.get("q") ?? "";
 const [page, setPage] = useState(0), [selected, setSelected] = useState<FleetEquipment | null>(null);
 const trigger = useRef<HTMLButtonElement | null>(null);
 const coverage = coverages.includes(params.get("coverage") as Coverage) ? params.get("coverage") as Coverage : undefined;
 const verdict = verdicts.includes(params.get("verdict") as Verdict) ? params.get("verdict") as Verdict : undefined;
 const deferred = useDeferredValue(search), query = useOverview(coverage, deferred);
 const items = query.data ?? [], filtered = verdict ? items.filter(item => item.verdict === verdict) : items;
 const pages = Math.max(1, Math.ceil(filtered.length / pageSize)), current = Math.min(page, pages - 1);
 const visible = filtered.slice(current * pageSize, (current + 1) * pageSize);
 function changeQuery(key: string, value?: string) { const next = new URLSearchParams(paramsRef.current); if (value) next.set(key, value); else next.delete(key); paramsRef.current = next; setParams(next, { replace: key === "q" }); setPage(0); }
 function filter(value?: Coverage) { changeQuery("coverage", value); }
 function formatWarranty(item: FleetEquipment) {
  if (!item.warranty_end) return "—";
  const date = new Intl.DateTimeFormat(i18n.language, { day: "2-digit", month: "2-digit", year: "numeric" }).format(new Date(`${item.warranty_end}T00:00:00`));
  if (item.coverage === "expiring_soon") return t("warrantyExpiring", { date, days: Math.max(item.days_left ?? 0, 0) });
  if (item.coverage === "expired") return t("warrantyEnded", { date });
  return t("warrantyUntil", { date });
 }
 return <div className="space-y-6">
  <header className="flex flex-wrap items-end justify-between gap-4"><div><h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">{t("heading")}</h1><p className="mt-2 text-sm text-muted">{t("summary")}</p></div><Button variant="outline" asChild><Link to="/documents">{t("addInvoice")}</Link></Button><div className="w-full"><FleetSummary/></div></header>
  <div className="flex flex-wrap items-center justify-between gap-4">
   <div className="flex min-w-0 flex-1 flex-wrap gap-4">
    <div role="group" aria-label={t("filterVerdict")} className="flex min-w-0 flex-wrap items-center gap-1.5">
     {([undefined, ...verdicts] as const).map(value => {
      const count = value ? items.filter(item => item.verdict === value).length : items.length;
      const active = verdict === value;
      return <button key={value ?? "all-verdicts"} type="button" aria-pressed={active} onClick={() => changeQuery("verdict", value)} className={`min-h-9 rounded-full px-3 py-1.5 text-sm font-medium transition-colors ${active ? "bg-accent text-white" : "bg-surface text-ink hover:bg-accent-soft"}`}>{value ? t(`enums:VerdictValue.${value}`) : t("verdictAll")} <span className={active ? "text-white/80" : "text-muted"}>{count}</span></button>;
     })}
    </div>
    <div role="group" aria-label={t("filter")} className="flex flex-wrap gap-1.5">
     {([undefined, ...coverages] as const).map(value => <button key={value ?? "all-coverage"} type="button" aria-pressed={coverage === value} onClick={() => filter(value)} className={`min-h-9 rounded-full px-3 py-1.5 text-sm font-medium ${coverage === value ? "bg-accent text-white" : "bg-surface text-ink hover:bg-accent-soft"}`}>{t(value ? `coverage.${value}` : "all")}</button>)}
    </div>
   </div>
   <label className="flex min-h-10 w-full items-center gap-2 rounded-xl border border-line bg-surface px-3 focus-within:ring-2 focus-within:ring-accent sm:w-72"><Search size={18} className="shrink-0 text-muted"/><input type="search" aria-label={t("search")} placeholder={t("search")} value={search} onChange={event => changeQuery("q", event.target.value)} className="min-w-0 flex-1 bg-transparent py-2 text-sm outline-none focus-visible:outline-none"/></label>
  </div>
  {query.isPending && <p role="status">{t("common:loading")}</p>}
  {query.isError && <div role="alert" className="rounded-[20px] border border-line bg-surface p-6"><p className="mb-3 text-bad">{t("error")}</p><Button onClick={() => void query.refetch()}>{t("common:refresh")}</Button></div>}
  {!query.isPending && !query.isError && !filtered.length && <Tile><EmptyState title={t("empty")} description={t("emptyHelp")}/></Tile>}
  <div className="grid items-start gap-5 xl:grid-cols-[minmax(0,1fr)_280px]" aria-busy={query.isFetching}>
   <Tile className="min-w-0 overflow-hidden p-0">
    <ul className="divide-y divide-line">
     <li aria-hidden="true" className="hidden md:grid md:grid-cols-[2fr_1fr_1fr_1.2fr_auto] gap-4 bg-canvas px-5 py-3 text-xs font-semibold text-muted"><span>{t("equipment")}</span><span>{t("serial")}</span><span>{t("assigned")}</span><span>{t("warranty")}</span><span>{t("status")}</span></li>
     {visible.map(item => <li key={item.equipment_id}>
      <button type="button" data-testid="equipment-tile" aria-label={item.label} aria-haspopup="dialog" onClick={event => { trigger.current = event.currentTarget; setSelected(item); }} className="grid w-full min-w-0 grid-cols-1 gap-2 px-4 py-4 text-left transition-colors hover:bg-accent-soft/40 focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-accent md:grid-cols-[2fr_1fr_1fr_1.2fr_auto] md:items-center md:gap-4 md:px-5">
       <span className="flex min-w-0 items-center gap-3"><EquipmentIcon category={item.category} size={40}/><span className="min-w-0"><span className="block font-semibold [overflow-wrap:anywhere]">{item.label}</span><span className="block text-xs text-muted md:hidden">{t("serial")}: {item.serial}</span></span></span>
       <span className="hidden min-w-0 truncate font-mono text-xs text-muted md:block">{item.serial}</span>
       <span className="hidden min-w-0 truncate text-sm text-muted md:block">{item.assigned_to?.name ?? t("unassigned")}</span>
       <span className="hidden min-w-0 text-sm text-muted md:block">{formatWarranty(item)}</span>
       <span className="flex flex-wrap items-center gap-2 md:justify-end"><VerdictBadge value={item.verdict}/>{item.open_case_id && <Pill className="bg-accent-soft px-2.5 py-1 text-xs text-accent">{t("caseInProgress")}</Pill>}</span>
       <span className="text-xs text-muted md:hidden">{item.assigned_to?.name ?? t("unassigned")} · {formatWarranty(item)}</span>
      </button>
     </li>)}
    </ul>
   </Tile>
   <FleetDistribution vertical/>
  </div>
  {filtered.length > 0 && <nav aria-label={t("pagination")} className="flex flex-wrap items-center justify-center gap-4"><Button variant="outline" disabled={current === 0} aria-label={t("previous")} onClick={() => setPage(current - 1)}><ChevronLeft size={18}/></Button><span role="status" className="text-sm text-muted">{t("page", { page: current + 1, pages, count: filtered.length })}</span><Button variant="outline" disabled={current + 1 >= pages} aria-label={t("next")} onClick={() => setPage(current + 1)}><ChevronRight size={18}/></Button></nav>}
  <EquipmentSheet item={selected} onClose={() => setSelected(null)} returnFocus={() => trigger.current?.focus()}/>
 </div>;
}
