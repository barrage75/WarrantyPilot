import { useRef, useState } from "react";
import { ArrowDownWideNarrow, ArrowUpWideNarrow, ChevronRight, Search, SlidersHorizontal } from "lucide-react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useQueries } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { useCases, useCase, useChecklist } from "@/api/hooks";
import { client, ApiError, unwrap } from "@/api/client";
import { apiErrorKey } from "@/api/errors";
import { useHumanAction } from "@/api/human";
import { HumanActions } from "@/components/case/HumanActions";
export { HumanActions } from "@/components/case/HumanActions";
import { useCaseStream } from "@/api/useCaseStream";
import { equipmentLabel, useCaseActions, useEquipment, usePeople, type CaseActionHistory } from "@/api/resources";
import type { StreamEventLocal } from "@/api/untyped";
import type { MethodResponse } from "openapi-fetch";
import { useOperator } from "@/operator-state";
import { RealityBadge, StatusBadge, VerdictBadge } from "@/components/Badges";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Tile } from "@/components/bento/Tile";
import { Pill } from "@/components/bento/Pill";
import { NumberTicker } from "@/components/bento/NumberTicker";
import { EmptyState } from "@/components/bento/EmptyState";
import { EquipmentIcon } from "@/components/bento/EquipmentIcon";
import { CaseStatus } from "@/components/case/CaseStatus";
import { CaseRealityPill } from "@/components/case/CaseRealityPill";
import { CaseEquipment } from "@/components/case/CaseEquipment";
import { AgentJourney } from "@/components/case/AgentJourney";
import { caseChannel } from "@/components/case/caseState";
import { formatDocumentFact } from "@/components/documents/facts";
import { Dialog, DialogClose, DialogContent, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { isTechnicalField, isTechnicalValue, technicalLabel } from "@/i18n/technical";
type Case = MethodResponse<typeof client, "get", "/api/cases/{case_id}">;
type Verdict = NonNullable<Case["verdict"]>;
const steps = ["repair_type", "backup_verified", "disk_encryption", "disk_handling", "accounts_and_mdm", "shipping_label", "return_inspection"] as const;
const conditions = ["under_threshold", "verdict_covered", "equipment_unambiguous", "no_possible_exclusion", "no_suspicious_signal", "low_commitment_action"] as const;
const short = (id?: string | null) => id?.slice(0, 8) ?? "—";
type PersonNames = ReadonlyMap<string, string>;
const personFields = new Set(["assigned_to", "by_person_id", "person_id", "reporter_id", "approver_id", "operator_id", "assignee_id"]);
const payloadEnums: Record<string, string[]> = {
 from: ["enums:CaseStatus"], to: ["enums:CaseStatus"], recommended_status: ["enums:CaseStatus"],
 status: ["enums:CaseStatus", "enums:ActionResultStatus", "eventValues", "technical:"],
 step: ["enums:ChecklistStepName"], badge: ["enums:RealityBadge"], reality: ["enums:RealityBadge"],
 channel: ["enums:Channel"], source: ["sources", "enums:FactSource", "enums:DocumentSource"],
 kind: ["actionKinds", "enums:IncidentKind", "enums:DocumentKind", "technical:"],
 reported_via: ["enums:IncidentReportedVia"], outcome: ["enums:PolicyOutcome", "technical:"],
 engine: ["technical:"], browser_engine: ["technical:"], portal_status: ["technical:"],
 code: ["technical:"], role: ["personRoles"],
};
function useEquipmentName() {
 const equipment = useEquipment();
 return (id?: string | null) => equipmentLabel(equipment.data?.find(item => item.id === id)) ?? short(id);
}
function proofCaseNumber(proof?: string | null) {
 if (!proof) return undefined;
 try { const value: unknown = JSON.parse(proof); return value && typeof value === "object" && "case_number" in value && typeof value.case_number === "string" ? value.case_number : undefined; } catch { return undefined; }
}
function BrowserStep({ payload }: { payload: Record<string, unknown> }) {
 const { t } = useTranslation("caseDetail");
 const [expanded, setExpanded] = useState(false);
 const closeButton = useRef<HTMLButtonElement>(null);
 const number = typeof payload.case_number === "string" ? payload.case_number : undefined;
 const screenshotUrl = typeof payload.screenshot_url === "string" ? payload.screenshot_url : undefined;
 const text = typeof payload.text === "string" ? payload.text : "";
 const engine = typeof payload.engine === "string" ? payload.engine : text.match(/^\[([a-z_]+)\]\s*/i)?.[1];
 const description = text.replace(/^\[[a-z_]+\]\s*/i, "");
 const engineLabel = engine ? t("technical:" + engine, { defaultValue: "" }) : "";
 const screenshotAlt = t("screenshotAlt");
 return <div className="mt-2 space-y-1 text-sm">{!isTechnicalValue(description) && <p>{engineLabel && <span className="font-medium">{engineLabel} · </span>}{description || "—"}</p>}{number && !isTechnicalValue(number) && <p className="font-semibold text-teal-900">{t("dellCase", { number })}</p>}{screenshotUrl && <><button type="button" aria-label={t("expandScreenshot")} className="block max-w-full cursor-zoom-in" onClick={() => setExpanded(true)}><img src={screenshotUrl} alt={screenshotAlt} className="max-h-64 max-w-full rounded border border-slate-200 object-contain"/></button><Dialog open={expanded} onOpenChange={setExpanded}><DialogContent className="w-auto max-w-[95vw] p-4" onOpenAutoFocus={event => { event.preventDefault(); closeButton.current?.focus(); }}><div className="flex items-center justify-between gap-4"><DialogTitle>{t("screenshot")}</DialogTitle><DialogClose ref={closeButton} autoFocus className="rounded border border-slate-300 px-3 py-1 text-sm">{t("close")}</DialogClose></div><DialogDescription className="sr-only">{screenshotAlt}</DialogDescription><img src={screenshotUrl} alt={screenshotAlt} className="max-h-[85vh] max-w-[90vw] rounded object-contain"/></DialogContent></Dialog></>}{((engine && !engineLabel) || Object.entries(payload).some(([key, value]) => isTechnicalField(key) || isTechnicalValue(value))) && <TechnicalDetails value={payload}/>}</div>;
}
function TechnicalDetails({ value }: { value: unknown }) {
 const { t, i18n } = useTranslation("caseDetail");
 function translateKeys(item: unknown): unknown {
  if (Array.isArray(item)) return item.map(translateKeys);
  if (item && typeof item === "object") return Object.fromEntries(Object.entries(item).map(([key, child]) => [technicalLabel(key, i18n.language), translateKeys(child)]));
  return item;
 }
 let structured = value;
 if (typeof value === "string") {
  try { structured = JSON.parse(value) as unknown; } catch { structured = value; }
 }
 return <details className="max-w-full text-sm"><summary className="cursor-pointer text-slate-600">{t("technicalDetails")}</summary><pre className="mt-2 max-w-full overflow-x-auto rounded bg-slate-50 p-3 text-xs">{JSON.stringify(translateKeys(structured), null, 2)}</pre></details>;
}
function ActionHistory({ history }: { history: CaseActionHistory }) {
 const { t, i18n } = useTranslation("caseDetail");
 const kind = t("actionKinds." + history.action.kind, { defaultValue: "" });
 return <li className="border-l-2 border-teal-600 pl-4"><div className="flex flex-wrap items-center gap-2"><h3 className="font-semibold">{t("enums:Channel." + history.action.channel)} · {kind || t("actionUnknown")}</h3><CaseRealityPill value={history.action.badge}/></div>{!kind && <TechnicalDetails value={{ kind: history.action.kind }}/>}<ul className="mt-2 space-y-2 text-sm">{history.results.map((result, index) => { const number = proofCaseNumber(result.proof); return <li key={result.id ?? index}><p className={result.status === "success" ? "text-green-800" : "text-red-800"}>{t("result")} : {t("enums:ActionResultStatus." + result.status, { defaultValue: technicalLabel(result.status, i18n.language) })}</p>{number && !isTechnicalValue(number) && <p className="font-semibold text-teal-900">{t("dellCase", { number })}</p>}{result.proof && <TechnicalDetails value={result.proof} />}{result.error && <details className="max-w-full text-red-800"><summary className="cursor-pointer">{t("technicalDetails")}</summary><pre className="mt-2 max-w-full overflow-x-auto whitespace-pre-wrap rounded bg-slate-50 p-3 text-xs">{result.error}</pre></details>}</li>; })}</ul></li>;
}
function useFormat() {
 const { i18n } = useTranslation();
 return (at?: string | null) => at && !Number.isNaN(Date.parse(at)) ? new Date(at).toLocaleString(i18n.language) : "—";
}
function ErrorMessage({ error }: { error: unknown }) { const { t } = useTranslation(); return <p role="alert" className="py-3 text-red-800">{t(apiErrorKey(error))}</p>; }
function Evidence({ verdict }: { verdict?: Verdict | null }) {
 const { t, i18n } = useTranslation("caseDetail");
 return <div><h3 className="my-3 font-semibold">{t("evidence")}</h3>{!verdict?.evidence?.length ? <p className="text-sm text-slate-500">{t("none")}</p> : <ul className="space-y-3">{verdict.evidence.map((e, i) => {
  const match = /^([\w.[\]]+)\s*:\s*([^\r\n]*)$/.exec(e.excerpt?.trim() ?? "");
  const raw = match?.[2].trim() ?? "";
  const value = /^(?:true|false)$/i.test(raw) ? raw.toLowerCase() === "true" : /^(?:null|none)$/i.test(raw) ? null : raw;
  const fact = match ? formatDocumentFact({ field: match[1], value }, i18n.language) : undefined;
  const generated = fact?.known;
  const technical = isTechnicalValue(e.excerpt);
  return <li key={e.id ?? i} className="border-l-2 border-teal-600 pl-3 text-sm"><p>{t("document")} <code>{short(e.document_id)}</code> · {t("page")} {e.page ?? "—"}</p>{technical ? <TechnicalDetails value={{ document_id: e.document_id, excerpt: e.excerpt }}/> : <blockquote className="mt-1 text-slate-600 [overflow-wrap:anywhere]">{generated ? t("evidenceFact", { label: fact.label, value: fact.formatted }) : e.excerpt}</blockquote>}{!technical && (e.document_id || generated) && <TechnicalDetails value={{ document_id: e.document_id, ...(generated ? { excerpt: e.excerpt } : {}) }}/>}</li>;
 })}</ul>}</div>;
}
function Reasons({ item }: { item: Case }) {
 const { t, i18n } = useTranslation("caseDetail");
 return <ul className="my-3 text-sm text-slate-600">{item.policy?.reasons?.map(reason => <li key={reason}>{t("reasons." + reason, { defaultValue: technicalLabel(reason, i18n.language) })}</li>)}</ul>;
}
export function Decisions() {
 const { t, i18n } = useTranslation("decisions");
 const query = useCases(), equipmentName = useEquipmentName();
 const cases = query.data ?? [];
 const checklists = useQueries({ queries: cases.map(item => ({ queryKey: ["checklist", item.id], queryFn: async () => unwrap(await client.GET("/api/cases/{case_id}/checklist", { params: { path: { case_id: item.id! } } })), enabled: !!item.id, retry: false })) });
 const queue = cases.filter((item, index) => {
  const checklistSteps = Object.values(checklists[index]?.data?.steps ?? {});
  const knownChecklist = checklistSteps.some(step => step.done || step.by_person_id || step.at);
  return ["awaiting_validation", "failed", "manual_takeover"].includes(item.status) ||
   (item.policy?.outcome === "blocked" && item.policy.reasons?.includes("data_checklist_incomplete")) ||
   (knownChecklist && checklistSteps.some(step => !step.done));
 });
 const pending = query.isPending || checklists.some(q => q.isPending && q.fetchStatus !== "idle");
 const checklistError = checklists.find(q => q.isError && !(q.error instanceof ApiError && q.error.status === 404))?.error;
 return <div className="space-y-5"><h1 className="text-3xl font-semibold">{t("heading")}</h1>{query.isError && <ErrorMessage error={query.error}/>} {checklistError && <ErrorMessage error={checklistError}/>}
 {pending && <p role="status">{t("common:loading")}</p>}
 {!pending && !query.isError && !checklistError && queue.length === 0 && <Card><h2 className="text-xl font-semibold">{t("empty")}</h2><p className="mt-2 text-slate-600">{t("emptyHelp")}</p></Card>}
 {queue.map(item => <Card key={item.id} className="space-y-4"><div className="flex flex-wrap items-center justify-between gap-3"><Link className="font-semibold text-teal-900 underline" to={"/cases/" + item.id}>{t("equipment")} {equipmentName(item.equipment_id)} · #{short(item.id)}</Link><div className="flex flex-wrap gap-2"><StatusBadge value={item.status}/><RealityBadge value={item.badge}/></div></div>
 {item.verdict && <><VerdictBadge value={item.verdict.value}/><p>{i18n.language.startsWith("fr") ? item.verdict.explanation_fr : item.verdict.explanation_en}</p></>}
 <p className="text-sm">{t("enums:Channel." + item.channel)}</p><Reasons item={item}/><Evidence verdict={item.verdict}/><HumanActions item={item}/><Link className="inline-block text-sm font-semibold text-teal-800 underline" to={"/cases/" + item.id}>{t("detail")}</Link></Card>)}</div>;
}
export function CasesPage() {
 const navigate = useNavigate();
 const { t } = useTranslation("cases"), date = useFormat();
 const query = useCases(), equipment = useEquipment();
 const [search, setSearch] = useState(""), [filters, setFilters] = useState<Record<string, string>>({}), [descending, setDescending] = useState(true), [filtersOpen, setFiltersOpen] = useState(false);
 const byId = new Map(equipment.data?.map(item => [item.id, item]));
 const rows = (query.data ?? []).filter(item => [item.id, equipmentLabel(byId.get(item.equipment_id ?? ""))].some(value => value?.toLowerCase().includes(search.toLowerCase())) && (!filters.status || item.status === filters.status) && (!filters.verdict || item.verdict?.value === filters.verdict) && (!filters.channel || caseChannel(item) === filters.channel) && (!filters.badge || item.badge === filters.badge)).sort((a, b) => ((Date.parse(b.updated_at ?? "") || 0) - (Date.parse(a.updated_at ?? "") || 0)) * (descending ? 1 : -1));
 const fields = { verdict: "VerdictValue", channel: "Channel", badge: "RealityBadge" };
 const statuses = Array.from(new Set(query.data?.map(item => item.status)));
 const filterCount = Object.values(filters).filter(Boolean).length;
 return <div className="min-w-0 space-y-6">
  <header className="flex flex-wrap items-end justify-between gap-4"><div><h1 className="text-4xl font-bold tracking-tight">{t("title")}</h1><p className="mt-2 text-ink/70">{t("subtitle")}</p></div><Pill className="gap-1.5"><NumberTicker value={rows.length}/><span>{t("caseCount", { count: rows.length })}</span></Pill></header>
  <section aria-label={t("filters")} className="space-y-4">
   <div className="flex flex-wrap items-center gap-3"><label className="relative min-w-0 flex-1"><span className="sr-only">{t("search")}</span><Search aria-hidden="true" size={18} className="pointer-events-none absolute left-4 top-3 text-muted"/><Input className="h-11 border-0 bg-surface pl-11" placeholder={t("searchPlaceholder")} value={search} onChange={e => setSearch(e.target.value)}/></label><Button variant="outline" className="sm:hidden" aria-expanded={filtersOpen} aria-controls="case-filters" onClick={() => setFiltersOpen(!filtersOpen)}><SlidersHorizontal size={16} aria-hidden="true"/>{t("filters")}{filterCount ? ` (${filterCount})` : ""}</Button><Button variant="outline" aria-label={t("updated")} aria-pressed={!descending} onClick={() => setDescending(!descending)}>{descending ? <ArrowDownWideNarrow size={18} aria-hidden="true"/> : <ArrowUpWideNarrow size={18} aria-hidden="true"/>}<span className="hidden sm:inline">{t("updated")}</span></Button></div>
   <div id="case-filters" className={`${filtersOpen ? "flex" : "hidden"} flex-col gap-4 sm:flex`}>
    <div role="group" aria-label={t("status")} className="flex flex-wrap gap-2">{["", ...statuses].map(value => <button key={value} type="button" aria-pressed={(filters.status ?? "") === value} className={`min-h-10 rounded-full px-4 py-2 text-sm font-medium ${(filters.status ?? "") === value ? "bg-ink text-white" : "bg-surface text-ink hover:bg-line"}`} onClick={() => setFilters(old => ({ ...old, status: value }))}>{value ? t("enums:CaseStatus." + value) : t("all")}</button>)}</div>
    <div className="flex flex-wrap items-center gap-3">{Object.entries(fields).map(([key, ns]) => <label className="flex max-w-full items-center gap-2 text-sm text-ink/70" key={key}>{t(key)}<select className="min-h-10 min-w-0 max-w-48 rounded-full border border-line bg-surface px-3 text-ink" value={filters[key] ?? ""} onChange={e => setFilters(old => ({ ...old, [key]: e.target.value }))}><option value="">{t("all")}</option>{Array.from(new Set((query.data ?? []).map(item => key === "verdict" ? item.verdict?.value : key === "channel" ? caseChannel(item) : item.badge))).filter((v): v is NonNullable<typeof v> => !!v).map(value => <option key={value} value={value}>{t("enums:" + ns + "." + value)}</option>)}</select></label>)}{filterCount > 0 && <button className="min-h-10 px-2 text-sm font-medium text-indigo-700 underline" onClick={() => setFilters({})}>{t("clearFilters")}</button>}</div>
   </div>
  </section>
  {query.isPending && <p role="status">{t("common:loading")}</p>}{query.isError && <ErrorMessage error={query.error}/>}
  <div className="grid min-w-0 gap-4 md:grid-cols-2 xl:grid-cols-3">{rows.map(item => { const device = byId.get(item.equipment_id ?? ""); return <Tile key={item.id} tabIndex={0} aria-label={item.id} highlight={item.status === "awaiting_validation"} className="min-w-0 cursor-pointer space-y-5" onClick={event => { if (!(event.target as HTMLElement).closest("a")) navigate("/cases/" + item.id); }} onKeyDown={event => { if (event.target === event.currentTarget && (event.key === "Enter" || event.key === " ")) { event.preventDefault(); navigate("/cases/" + item.id); } }}>
   <div className="flex items-start justify-between gap-3"><EquipmentIcon category={device?.category ?? "package"} size={44}/><CaseRealityPill value={item.badge}/></div>
   <div><h2 className="text-xl font-semibold tracking-tight [overflow-wrap:anywhere]">{device ? `${device.brand} ${device.model}` : t("equipmentUnknown")}</h2><p className="mt-1 text-sm text-muted [overflow-wrap:anywhere]">{device?.serial ?? "—"}</p></div>
   <div className="flex flex-wrap items-center gap-3"><CaseStatus status={item.status}/>{item.verdict && <Pill className={`px-3 py-1 ${item.verdict.value === "covered" ? "bg-ok/10 text-emerald-800" : ["not_covered", "out_of_manufacturer"].includes(item.verdict.value) ? "bg-bad/10 text-red-800" : "bg-warn/15 text-amber-900"}`}>{t("enums:VerdictValue." + item.verdict.value)}</Pill>}</div>
   <div className="border-t border-line pt-4 text-sm"><p className="text-muted">{t("enums:Channel." + caseChannel(item))}</p><div className="mt-2 flex flex-wrap items-center justify-between gap-2"><Link className="inline-flex min-h-10 items-center gap-1 font-semibold text-indigo-700" to={"/cases/" + item.id} aria-label={short(item.id)}>{t("id")} #{short(item.id)}<ChevronRight size={16} aria-hidden="true"/></Link><time className="text-xs text-muted" dateTime={item.updated_at}>{date(item.updated_at)}</time></div></div>
  </Tile>; })}</div>
  {!query.isPending && !query.isError && !rows.length && <Tile><EmptyState title={t("empty")} description={t("emptyHelp")} action={<Button variant="outline" onClick={() => { setFilters({}); setSearch(""); }}>{t("clearFilters")}</Button>}/></Tile>}
 </div>;
}
function Checklist({ id, personNames }: { id: string; personNames: PersonNames }) {
 const { t } = useTranslation("caseDetail"), date = useFormat();
 const query = useChecklist(id), action = useHumanAction(id), { personId } = useOperator();
 if (query.error instanceof ApiError && query.error.status === 404) return null;
 return <Card><h2 className="mb-4 text-xl font-semibold">{t("checklist")}</h2>{query.isPending && <p>{t("common:loading")}</p>}{query.isError && <ErrorMessage error={query.error}/>}
 {!personId && <p className="mb-4 text-sm text-amber-900">{t("common:identityRequired")}</p>}
 {query.data && <><p role="status" aria-live="polite" className="mb-5 rounded-md border border-amber-300 bg-amber-50 p-3 text-sm font-medium text-amber-950">{steps.every(step => query.data.steps?.[step]?.done) ? t("checklistComplete") : t("checklistIncomplete", { count: steps.filter(step => query.data.steps?.[step]?.done).length })}</p><ol className="space-y-5">{steps.map((step, index) => { const data = query.data.steps?.[step], name = data?.by_person_id ? personNames.get(data.by_person_id) : undefined; return <li key={step} className="border-b border-slate-100 pb-4"><h3 className="font-semibold">{index + 1}. {t("enums:ChecklistStepName." + step)} {data?.done ? "✓" : ""}</h3><p className="my-1 text-sm text-slate-600">{t("steps." + step)}</p><p className="text-sm">{t("who")}: {t(["repair_type", "shipping_label"].includes(step) ? "agent" : "human")}</p>{data?.done ? <><p className="mt-2 text-sm [overflow-wrap:anywhere]">{name && <>{name} · </>}{date(data.at)}</p>{data.by_person_id && <TechnicalDetails value={{ by_person_id: data.by_person_id }}/>}</> : <Button className="mt-2" variant="outline" disabled={!personId || action.isPending} onClick={() => action.mutate({ kind: "checklist", step }, { onSuccess: () => toast.success(t("actionSuccess")), onError: error => toast.error(t(apiErrorKey(error))) })}>{t("complete")}</Button>}</li>; })}</ol></>}{action.isError && <ErrorMessage error={action.error}/>}</Card>;
}
function Payload({ payload, personNames }: { payload: Record<string, unknown>; personNames: PersonNames }) {
 const { t } = useTranslation("caseDetail");
 function readable(value: unknown, key: string): string | undefined {
  if (personFields.has(key)) return typeof value === "string" ? personNames.get(value) : undefined;
  if (value === null || value === undefined) return "—";
  if (typeof value === "boolean") return t(value ? "eventValues.yes" : "eventValues.no");
  const namespaces = payloadEnums[key];
  if (namespaces) {
   const code = key === "source" ? String(value).replaceAll(" ", "_") : String(value);
   for (const namespace of namespaces) {
    const label = t(namespace + (namespace.endsWith(":") ? "" : ".") + code, { defaultValue: "" });
    if (label) return label;
   }
   return undefined;
  }
  if (key === "reason") return t("reasons." + String(value), { defaultValue: String(value) });
  return String(value);
 }
 const visible = Object.entries(payload).flatMap(([key, value]) => {
  if (!personFields.has(key) && (isTechnicalField(key) || isTechnicalValue(value) || (value !== null && typeof value === "object"))) return [];
  const fieldLabel = t("payloadLabels." + key, { defaultValue: "" }) || t("technical:" + key, { defaultValue: "" });
  if (!fieldLabel) return [];
  const label = readable(value, key);
  return label === undefined ? [] : [{ key, value, label, fieldLabel }];
 });
 const hasTechnical = visible.length !== Object.keys(payload).length || Object.keys(payload).some(key => personFields.has(key));
 return <>{visible.length > 0 && <dl className="mt-2 space-y-1 text-sm text-slate-600 [overflow-wrap:anywhere]">{visible.map(({ key, value, label, fieldLabel }) => <div key={key}><dt className="inline font-medium">{fieldLabel}: </dt><dd className="inline">{key === "badge" && (value === "real" || value === "reproduction" || value === "simulated") ? <CaseRealityPill value={value}/> : label}</dd></div>)}</dl>}{hasTechnical && <TechnicalDetails value={payload}/>}</>;
}
function EventRow({ event, personNames }: { event: StreamEventLocal; personNames: PersonNames }) {
 const { t, i18n } = useTranslation("caseDetail"), date = useFormat();
 const human = event.actor.startsWith("human:"), knownActor = ["agent", "system", "human"].includes(event.actor);
 const actor = human ? personNames.get(event.actor.slice(6)) ?? t("human") : knownActor ? t(event.actor) : t("actorUnknown");
 return <li className="border-l-2 border-teal-600 pl-4"><h3 className="font-semibold">{t("enums:EventType." + event.type, { defaultValue: technicalLabel(event.type, i18n.language) })}</h3><p className="text-xs text-slate-500">{date(event.at)} · {actor} · #{event.seq}</p>{event.type === "action_step" ? <BrowserStep payload={event.payload}/> : <Payload payload={event.payload} personNames={personNames}/>}{!knownActor && <TechnicalDetails value={{ actor: event.actor }}/>}</li>;
}
export function CaseDetail() {
 const { id = "" } = useParams(), { t, i18n } = useTranslation("caseDetail"), date = useFormat();
 const query = useCase(id), stream = useCaseStream(id), history = useCaseActions(id), equipmentName = useEquipmentName();
 const people = usePeople(), { user } = useOperator();
 const personNames = new Map<string, string>();
 for (const person of people.data ?? []) if (person.id && person.name) personNames.set(person.id, person.name);
 if (user && !personNames.has(user.person_id)) personNames.set(user.person_id, user.name);
 const item = query.data, verdict = item?.verdict;
 if (query.isPending) return <p>{t("common:loading")}</p>;
 if (query.isError) return <ErrorMessage error={query.error}/>;
 if (!item) return null;
 return <div className="min-w-0 space-y-6"><Link className="inline-flex min-h-10 items-center text-sm font-medium text-indigo-700 underline" to="/cases">{t("back")}</Link><header className={`min-w-0 space-y-5 rounded-[28px] bg-surface p-6 sm:p-8 ${item.status === "awaiting_validation" ? "ring-2 ring-accent" : ""}`}>
 <CaseEquipment equipmentId={item.equipment_id}/>
 <div><h1 className="text-3xl font-bold tracking-tight sm:text-4xl"><span className="mb-2 block text-sm font-medium text-muted">{t("title")} #{short(item.id)}</span><span className="[overflow-wrap:anywhere]">{equipmentName(item.equipment_id)}</span></h1></div>
 <div className="flex flex-wrap items-center gap-3"><CaseStatus status={item.status}/><CaseRealityPill value={item.badge}/><Pill className="bg-canvas">{t("enums:Channel." + caseChannel(item))}</Pill></div>
 <p className="text-sm text-muted">{t("created")}: {date(item.created_at)} · {t("updated")}: {date(item.updated_at)}</p></header>
 <AgentJourney item={item} events={stream.data ?? []}/>
 {["awaiting_validation", "failed", "manual_takeover"].includes(item.status) && <Card><h2 className="mb-4 text-xl font-semibold">{t("yourDecision")}</h2><HumanActions item={item} section="decision"/></Card>}
 <div className="grid items-start gap-6 xl:grid-cols-2">
  <Card>
   <h2 className="mb-4 text-xl font-semibold">{t("verdict")}</h2>
   {verdict ? <>
    <VerdictBadge value={verdict.value}/>
    <p className="my-3 [overflow-wrap:anywhere]">{i18n.language.startsWith("fr") ? verdict.explanation_fr : verdict.explanation_en}</p>
    <details className="text-sm"><summary className="cursor-pointer text-slate-600">{t("technicalDetails")}</summary><dl className="mt-2 max-w-full overflow-x-auto rounded bg-slate-50 p-3 text-xs"><dt className="font-semibold">{technicalLabel("rule_id", i18n.language)}</dt><dd className="[overflow-wrap:anywhere]">{verdict.rule_id ?? "—"}</dd><dt className="mt-2 font-semibold">{technicalLabel("rule_version", i18n.language)}</dt><dd className="[overflow-wrap:anywhere]">{verdict.rule_version ?? "—"}</dd></dl></details>
    <ul className="my-4 space-y-3">{verdict.checks?.map((check, index) => <li key={check.id ?? index}><span className={check.passed === true ? "text-green-800" : check.passed === false ? "text-red-800" : "text-slate-600"}>{check.passed === true ? "✓" : check.passed === false ? "✗" : t("undetermined")}</span> {t("checkNames." + check.name, { defaultValue: technicalLabel(check.name, i18n.language) })}{isTechnicalValue(check.detail) ? <TechnicalDetails value={{ detail: check.detail }}/> : <p className="text-sm text-slate-600 [overflow-wrap:anywhere]">{t("checkDetails." + check.name, { defaultValue: check.detail })}</p>}</li>)}</ul>
    <h3 className="font-semibold">{t("missing")}</h3><p className="[overflow-wrap:anywhere]">{verdict.missing?.map(value => technicalLabel(value, i18n.language)).join(" · ") || t("none")}</p>
    <h3 className="mt-3 font-semibold">{t("exclusions")}</h3><p className="[overflow-wrap:anywhere]">{verdict.possible_exclusions?.map(value => technicalLabel(value, i18n.language)).join(" · ") || t("none")}</p>
    <Evidence verdict={verdict}/>
   </> : <p>{t("none")}</p>}
  </Card>
  <Card><h2 className="mb-4 text-xl font-semibold">{t("policy")}</h2>{item.policy ? <><p className="font-semibold">{t("enums:PolicyOutcome." + item.policy.outcome)}</p><Reasons item={item}/><ul className="space-y-3">{conditions.map(key => <li key={key}><span className={item.policy!.conditions[key] ? "text-green-800" : "text-red-800"}>{item.policy!.conditions[key] === true ? "✓" : item.policy!.conditions[key] === false ? "✗" : t("undetermined")}</span> {t("conditions." + key)}</li>)}</ul></> : <p>{t("none")}</p>}</Card>
 </div>
 <Checklist id={id} personNames={personNames}/>
 <Card><h2 className="text-xl font-semibold">{t("actions")}</h2><p className="my-3 text-sm text-slate-600">{t("actionsNote")}</p>{history.isError && <ErrorMessage error={history.error}/>}{history.data && !history.data.length && <p>{t("none")}</p>}<ol className="space-y-5">{history.data?.map((entry, index) => <ActionHistory key={entry.action.id ?? index} history={entry}/>)}</ol></Card>
 {["sent", "tracked"].includes(item.status) && <Card><h2 className="mb-4 text-xl font-semibold">{t("resolution")}</h2><HumanActions item={item} section="resolution"/></Card>}
 <Card><div className="mb-5 flex flex-wrap justify-between gap-3"><h2 className="text-xl font-semibold">{t("timeline")}</h2><span role="status" className={stream.connection === "open" ? "text-green-800" : "text-amber-900"}>{t(stream.mode === "poll" ? "polling" : stream.connection === "open" ? "liveSse" : "reconnecting")}</span></div>{stream.isError && <ErrorMessage error={stream.error}/>}<ol className="space-y-6">{stream.data?.map(e => <EventRow key={e.seq} event={e} personNames={personNames}/>)}</ol>{!stream.isPending && !stream.data?.length && <p>{t("none")}</p>}</Card></div>;
}
