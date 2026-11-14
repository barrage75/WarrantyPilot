import { useQueries } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useCases } from "@/api/hooks";
import { ApiError, client, unwrap } from "@/api/client";
import { apiErrorKey } from "@/api/errors";
import { equipmentLabel, useEquipment } from "@/api/resources";
import { useOperator } from "@/operator-state";
import { HumanActions } from "@/components/case/HumanActions";
import { RealityBadge, StatusBadge, VerdictBadge } from "@/components/Badges";
import { Tile } from "@/components/bento/Tile";
import { EmptyState } from "@/components/bento/EmptyState";
import { EquipmentIcon } from "@/components/bento/EquipmentIcon";
import { WarrantyRing } from "@/components/bento/WarrantyRing";
import { DecisionBeam } from "@/components/parc/DecisionBeam";
import { NotificationList } from "@/components/parc/NotificationList";
import { FleetSummary } from "@/components/parc/FleetSummary";
import { useOverview } from "@/components/parc/data";
import { isTechnicalValue, technicalLabel } from "@/i18n/technical";

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
 return <div className="space-y-5"><h2 className="text-xl font-semibold tracking-tight">{t("heading")}</h2>
  {query.isError && <p role="alert" className="text-red-800">{t(apiErrorKey(query.error))}</p>}{!!checklistError && <p role="alert" className="text-red-800">{t(apiErrorKey(checklistError))}</p>}
  {pending && <p role="status">{t("common:loading")}</p>}
  {!pending && !query.isError && !checklistError && queue.length === 0 && <Tile><EmptyState title={t("empty")} description={t("emptyHelp")}/></Tile>}
  <div className="space-y-4">{queue.map(item => {
   const device = equipment.data?.find(device => device.id === item.equipment_id), warranty = overview.data?.find(device => device.equipment_id === item.equipment_id);
   return <DecisionBeam key={item.id} active={!!beamId && item.id === beamId}>
    <div className="flex items-start justify-between gap-4"><EquipmentIcon category={device?.category ?? "package"} size={48}/>{warranty && <WarrantyRing daysLeft={warranty.days_left} coverage={warranty.coverage}/>}</div>
    <div className="flex flex-wrap items-start justify-between gap-3"><Link className="font-semibold text-ink underline underline-offset-4" to={`/cases/${item.id}`}>{t("equipment")} {equipmentLabel(device) ?? item.equipment_id?.slice(0, 8)} · #{item.id?.slice(0, 8)}</Link><div className="flex flex-wrap gap-2"><StatusBadge value={item.status}/><RealityBadge value={item.badge}/></div></div>
    <div className="flex flex-wrap items-center gap-3"><HumanActions item={item} beam={false}/><Link className="inline-block text-sm font-semibold text-ink underline underline-offset-4" to={`/cases/${item.id}`}>{t("detail")}</Link></div>
    {item.verdict && <><VerdictBadge value={item.verdict.value}/><p>{i18n.language.startsWith("fr") ? item.verdict.explanation_fr : item.verdict.explanation_en}</p></>}
    <p className="text-sm text-muted">{t(`enums:Channel.${item.channel}`)}</p>
    <ul className="space-y-1 text-sm text-muted">{item.policy?.reasons?.map(reason => <li key={reason}>{t(`caseDetail:reasons.${reason}`, { defaultValue: technicalLabel(reason, i18n.language) })}</li>)}</ul>
    <details className="rounded-2xl bg-canvas p-4"><summary className="cursor-pointer text-sm font-semibold">{t("caseDetail:evidence")} ({item.verdict?.evidence?.length ?? 0})</summary>{!item.verdict?.evidence?.length ? <p className="mt-2 text-sm text-ink/70">{t("caseDetail:none")}</p> : <ul className="mt-3 space-y-3 text-sm">{item.verdict.evidence.map((evidence, index) => <li key={evidence.id ?? index} className="border-l-2 border-accent pl-3">{evidence.document_id && <p>{t("caseDetail:document")} {evidence.document_id.slice(0, 8)}{evidence.page != null && <> · {t("caseDetail:page")} {evidence.page}</>}</p>}{!isTechnicalValue(evidence.excerpt) && <blockquote className="mt-1 text-ink/70">{evidence.excerpt}</blockquote>}<details className="mt-1"><summary className="cursor-pointer text-ink/70">{t("caseDetail:technicalDetails")}</summary><pre className="overflow-auto whitespace-pre-wrap break-all text-xs">{JSON.stringify(evidence, null, 2)}</pre></details></li>)}</ul>}</details>
   </DecisionBeam>;
  })}</div>
 </div>;
}

export default function Home() {
 const { t } = useTranslation("home"), { user } = useOperator(), expiring = useOverview("expiring_soon");
 return <div className="space-y-7"><header className="flex flex-wrap items-end justify-between gap-4"><div><p className="mb-2 text-sm text-ink/70">{t("greeting", { name: user?.name.split(" ")[0] ?? "" })}</p><h1 className="text-3xl font-bold tracking-tight sm:text-4xl">{t("heading")}</h1></div><FleetSummary/></header>
  <div className="grid items-start gap-5 xl:grid-cols-3"><div className="min-w-0 xl:col-span-2"><Decisions/></div><Tile className="min-w-0"><h2 className="mb-5 text-xl font-semibold tracking-tight">{t("watch")}</h2><NotificationList/></Tile></div>
  <Tile><div className="mb-5 flex flex-wrap items-center justify-between gap-3"><h2 className="text-xl font-semibold tracking-tight">{t("expiring")}</h2><Link className="text-sm font-medium underline underline-offset-4" to="/parc?coverage=expiring_soon">{t("viewFleet")}</Link></div>
   {expiring.isPending && <p role="status">{t("common:loading")}</p>}{expiring.isError && <p role="alert" className="text-red-800">{t("expiringError")}</p>}{expiring.data?.length === 0 && <EmptyState title={t("noExpiring")}/>}
   <div className="flex flex-wrap gap-3">{expiring.data?.slice(0, 8).map(item => <Link key={item.equipment_id} to={`/parc?q=${encodeURIComponent(item.serial)}`} className="flex max-w-full items-center gap-3 rounded-full bg-canvas py-2 pl-3 pr-5"><EquipmentIcon category={item.category} size={24}/><span className="min-w-0 text-sm"><span className="block truncate font-semibold">{item.label}</span><span className="text-muted">{t("days", { count: item.days_left ?? 0 })}</span></span></Link>)}</div>
  </Tile>
 </div>;
}
