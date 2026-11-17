import { useQueries } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { ChevronRight, Wrench } from "lucide-react";
import { useCases } from "@/api/hooks";
import { ApiError, client, unwrap } from "@/api/client";
import { apiErrorKey } from "@/api/errors";
import { useEquipment } from "@/api/resources";
import { useOperator } from "@/operator-state";
import { HumanActions } from "@/components/case/HumanActions";
import { StatusBadge, VerdictBadge } from "@/components/Badges";
import { CaseRealityPill as RealityPill } from "@/components/case/CaseRealityPill";
import { Tile } from "@/components/bento/Tile";
import { Pill } from "@/components/bento/Pill";
import { EmptyState } from "@/components/bento/EmptyState";
import { EquipmentIcon } from "@/components/bento/EquipmentIcon";
import { NumberTicker } from "@/components/bento/NumberTicker";
import { DecisionBeam } from "@/components/parc/DecisionBeam";
import { NotificationList } from "@/components/parc/NotificationList";
import { FleetDistribution } from "@/components/parc/FleetDistribution";
import { useOverview, useSavings } from "@/components/parc/data";
import { isTechnicalValue, technicalLabel } from "@/i18n/technical";
import { Button } from "@/components/ui/button";
import { CaseStatus } from "@/components/case/CaseStatus";
import heroImage from "@/assets/iso/hero.webp";

export function Decisions() {
 const { t, i18n } = useTranslation("decisions");
 const query = useCases(), equipment = useEquipment(), overview = useOverview();
 const cases = query.data ?? [];
 const checklists = useQueries({ queries: cases.map(item => ({ queryKey: ["checklist", item.id], queryFn: async () => unwrap(await client.GET("/api/cases/{case_id}/checklist", { params: { path: { case_id: item.id! } } })), enabled: !!item.id, retry: false })) });
 const queue = cases.filter((item, index) => {
  const steps = Object.values(checklists[index]?.data?.steps ?? {});
  const known = steps.some(step => step.done || step.by_person_id || step.at);
  return ["awaiting_validation", "failed", "manual_takeover"].includes(item.status) || (item.policy?.outcome === "blocked" && item.policy.reasons?.includes("data_checklist_incomplete")) || (known && steps.some(step => !step.done));
 });
 const pending = query.isPending || checklists.some(q => q.isPending && q.fetchStatus !== "idle");
 const checklistError = checklists.find(q => q.isError && !(q.error instanceof ApiError && q.error.status === 404))?.error;
 const beamId = queue.find(item => item.status === "awaiting_validation")?.id;
 return <Tile role="region" className="min-w-0 space-y-4 p-4 sm:p-5" aria-labelledby="decisions-heading">
  <header className="flex items-center justify-between gap-3"><h2 id="decisions-heading" className="text-xl font-semibold tracking-tight">{t("heading")}</h2><Pill className="font-semibold tabular-nums" aria-label={t("queueCount", { count: queue.length })}><NumberTicker value={queue.length}/></Pill></header>
  {query.isError && <p role="alert" className="text-bad">{t(apiErrorKey(query.error))}</p>}{!!checklistError && <p role="alert" className="text-bad">{t(apiErrorKey(checklistError))}</p>}
  {pending && <p role="status">{t("common:loading")}</p>}
  {!pending && !query.isError && !checklistError && queue.length === 0 && <div className="rounded-xl bg-canvas p-4"><EmptyState title={t("empty")} description={t("emptyHelp")}/></div>}
  <div className="divide-y divide-line">{queue.map(item => {
   const device = equipment.data?.find(device => device.id === item.equipment_id), warranty = overview.data?.find(device => device.equipment_id === item.equipment_id);
   const label = warranty?.label ?? ([device?.brand, device?.model].filter(Boolean).join(" ") || t("common:unknown"));
   return <DecisionBeam key={item.id} active={!!beamId && item.id === beamId}>
    <div className="space-y-3">
     <div className="flex min-w-0 flex-wrap items-center gap-3 md:flex-nowrap">
      <EquipmentIcon category={device?.category ?? "package"} size={40}/>
      <div className="min-w-0 flex-1">
       <div className="flex flex-wrap items-center gap-x-2 gap-y-1"><Link className="font-semibold text-ink underline underline-offset-4" to={`/cases/${item.id}`}>{label}</Link><StatusBadge value={item.status}/><RealityPill value={item.badge}/></div>
       <p className="mt-1 text-sm text-muted">{[warranty?.assigned_to?.name, device?.serial].filter(Boolean).join(" · ")}</p>
      </div>
      <div className="w-full md:ml-auto md:w-auto md:shrink-0"><div className="flex flex-wrap items-center gap-2 md:justify-end"><HumanActions item={item} beam={false} section="decision"/><Link className="inline-flex min-h-9 items-center text-sm font-semibold text-accent underline underline-offset-4" to={`/cases/${item.id}`}>{t("detail")}</Link></div></div>
     </div>
     <div className="grid gap-2 sm:grid-cols-2">
      <details className="min-w-0 rounded-xl bg-canvas px-3 py-2">
      <summary className="cursor-pointer text-sm font-semibold">{t("details")}</summary>
      <div className="mt-3 space-y-2 text-sm">
       {item.verdict && <><VerdictBadge value={item.verdict.value}/><p className="text-ink">{i18n.language.startsWith("fr") ? item.verdict.explanation_fr : item.verdict.explanation_en}</p></>}
       <p className="text-muted">{t(`enums:Channel.${item.channel}`)}</p>
       <ul className="space-y-1 text-muted">{item.policy?.reasons?.map(reason => <li key={reason}>{t(`caseDetail:reasons.${reason}`, { defaultValue: technicalLabel(reason, i18n.language) })}</li>)}</ul>
     </div>
     </details>
      <details className="min-w-0 rounded-xl bg-canvas px-3 py-2 text-sm"><summary className="cursor-pointer font-semibold">{t("caseDetail:evidence")} ({item.verdict?.evidence?.length ?? 0})</summary>{!item.verdict?.evidence?.length ? <p className="mt-1 text-muted">{t("caseDetail:none")}</p> : <ul className="mt-2 space-y-2">{item.verdict.evidence.map((evidence, index) => <li key={evidence.id ?? index} className="border-l-2 border-accent pl-3">{evidence.document_id && <p>{t("caseDetail:document")} {evidence.document_id.slice(0, 8)}{evidence.page != null && <> · {t("caseDetail:page")} {evidence.page}</>}</p>}{!isTechnicalValue(evidence.excerpt) && <blockquote className="mt-1 text-muted">{evidence.excerpt}</blockquote>}<details className="mt-1"><summary className="cursor-pointer text-muted">{t("caseDetail:technicalDetails")}</summary><pre className="max-w-full overflow-x-auto whitespace-pre-wrap break-all text-xs">{JSON.stringify(evidence, null, 2)}</pre></details></li>)}</ul>}</details>
     </div>
    </div>
   </DecisionBeam>;
  })}</div>
 </Tile>;
}

export default function Home() {
 const { t } = useTranslation(["home", "common"]), { user } = useOperator();
 const expiring = useOverview("expiring_soon"), overview = useOverview(), savings = useSavings(), casesQuery = useCases(), equipment = useEquipment();
 const avoidable = savings.data?.possible_savings_eur ?? 0;
 const verifyCount = overview.data?.filter(item => item.verdict === "to_verify").length ?? 0;
 const openCases = (casesQuery.data ?? []).filter(item => !["resolved", "cancelled"].includes(item.status)).slice(0, 5);
 const kpis = [
  { label: t("covered"), value: savings.data?.covered_equipment_eur, to: "/dashboard", icon: "laptop" },
  { label: t("avoidable"), value: savings.data ? avoidable : undefined, to: "/purchase-guard", icon: "package" },
  { label: t("expiringKpi"), value: expiring.data?.length, to: "/parc?coverage=expiring_soon", icon: "calendar" },
  { label: t("toVerify"), value: overview.data ? verifyCount : undefined, to: "/parc?verdict=to_verify", icon: "shield" },
 ] as const;
 return <div className="space-y-7">
  <header className="grid items-center gap-5 md:grid-cols-[minmax(0,1fr)_minmax(240px,420px)]">
   <div className="min-w-0"><h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">{t("greeting", { name: user?.name.split(" ")[0] ?? "" })}</h1><p className="mt-2 max-w-xl text-muted">{t("heading")}</p>
    <div className="mt-5 flex flex-wrap items-center gap-3"><Button asChild><Link to="/chat"><Wrench size={17}/>{t("reportFault")}<ChevronRight size={16}/></Link></Button><span className="rounded-full bg-idle-soft px-3 py-1.5 text-xs font-medium text-muted">{t("demoData")}</span></div>
   </div>
   <img src={heroImage} alt="" aria-hidden="true" className="hidden h-52 w-full object-contain md:block lg:h-56"/>
  </header>
  <section aria-label={t("overview")} className="grid grid-cols-2 gap-2 sm:gap-3 xl:grid-cols-4">
   {kpis.map(({ label, value, to, icon }) => <Tile key={label} className="p-3 sm:p-4">
    <Link to={to} className="flex min-w-0 items-center gap-2 rounded-xl focus-visible:ring-2 focus-visible:ring-accent sm:gap-3">
     <EquipmentIcon category={icon} size={36} className="sm:hidden"/>
     <EquipmentIcon category={icon} size={48} className="hidden sm:block"/>
     <span className="min-w-0"><span className="block text-xl font-semibold tabular-nums sm:text-2xl">{value === undefined ? "—" : <NumberTicker value={value} currency={icon === "laptop" || icon === "package" ? "EUR" : undefined}/>}</span><span className="mt-1 block text-xs leading-snug text-muted sm:text-sm">{label}</span></span>
    </Link>
   </Tile>)}
  </section>
  <div className="grid items-start gap-5 xl:grid-cols-2"><Decisions/>
   <Tile className="min-w-0"><div className="mb-4 flex items-center justify-between gap-3"><h2 className="text-xl font-semibold tracking-tight">{t("inProgress")}</h2><Link className="text-sm font-semibold text-accent underline underline-offset-4" to="/cases">{t("viewCases")}</Link></div>
    {casesQuery.isPending && <p role="status">{t("common:loading")}</p>}{casesQuery.isError && <p role="alert">{t("casesError")}</p>}
    {!casesQuery.isPending && openCases.length === 0 && <EmptyState title={t("noneInProgress")}/>}
    <ul className="divide-y divide-line">{openCases.map(item => {
     const device = equipmentMeta(item.equipment_id, equipment.data);
     return <li key={item.id}><Link to={`/cases/${item.id}`} className="flex min-w-0 items-center gap-3 py-3 first:pt-0">
      <EquipmentIcon category={device.category} size={44}/><span className="min-w-0 flex-1"><span className="block truncate font-semibold">{device.label}</span><span className="block truncate text-sm text-muted">{t(`enums:Channel.${item.channel}`)}</span><span className="mt-2 flex flex-wrap items-center gap-2"><CaseStatus status={item.status}/><RealityPill value={item.badge}/></span></span><ChevronRight size={16} className="shrink-0 text-muted"/>
     </Link></li>;
    })}</ul>
   </Tile>
  </div>
  <div className="grid items-start gap-5 xl:grid-cols-2">
   <Tile className="min-w-0"><h2 className="mb-4 text-xl font-semibold tracking-tight">{t("watch")}</h2><NotificationList/></Tile>
   <Tile className="min-w-0"><div className="mb-4 flex flex-wrap items-center justify-between gap-3"><h2 className="text-xl font-semibold tracking-tight">{t("expiring")}</h2><Link className="text-sm font-medium text-accent underline underline-offset-4" to="/parc?coverage=expiring_soon">{t("viewFleet")}</Link></div>
    {expiring.isPending && <p role="status">{t("common:loading")}</p>}{expiring.isError && <p role="alert" className="text-bad">{t("expiringError")}</p>}{expiring.data?.length === 0 && <EmptyState title={t("noExpiring")}/>}
    <ul className="divide-y divide-line">{expiring.data?.slice(0, 6).map(item => <li key={item.equipment_id}><Link to={`/parc?q=${encodeURIComponent(item.serial)}`} className="flex items-center gap-3 py-3 first:pt-0">
     <EquipmentIcon category={item.category} size={40}/><span className="min-w-0 flex-1"><span className="block truncate font-semibold">{item.label}</span><span className="block truncate text-sm text-muted">{[item.assigned_to?.name, item.serial].filter(Boolean).join(" · ")}</span></span><span className="shrink-0 text-sm font-medium text-warn">{t("days", { count: item.days_left ?? 0 })}</span>
    </Link></li>)}</ul>
   </Tile>
  </div>
  <FleetDistribution/>
 </div>;
}

function equipmentMeta(id: string | null | undefined, equipment?: { id?: string | null; brand?: string; model?: string; category?: string }[]) {
 const item = equipment?.find(device => device.id === id);
 return { label: item ? `${item.brand} ${item.model}` : "—", category: item?.category ?? "package" };
}
