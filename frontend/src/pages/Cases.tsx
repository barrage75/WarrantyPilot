import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useQueries } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { useCases, useCase, useChecklist } from "@/api/hooks";
import { client, ApiError, unwrap } from "@/api/client";
import { apiErrorKey } from "@/api/errors";
import { useHumanAction, type HumanAction } from "@/api/human";
import { useCaseStream } from "@/api/useCaseStream";
import { equipmentLabel, useCaseActions, useEquipment, type CaseActionHistory } from "@/api/resources";
import type { StreamEventLocal } from "@/api/untyped";
import type { MethodResponse } from "openapi-fetch";
import { useOperator } from "@/operator-state";
import { RealityBadge, StatusBadge, VerdictBadge } from "@/components/Badges";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Table } from "@/components/ui/table";
import { Dialog, DialogContent, DialogTitle, DialogDescription } from "@/components/ui/dialog";
type Case = MethodResponse<typeof client, "get", "/api/cases/{case_id}">;
type Verdict = NonNullable<Case["verdict"]>;
const steps = ["repair_type", "backup_verified", "disk_encryption", "disk_handling", "accounts_and_mdm", "shipping_label", "return_inspection"] as const;
const conditions = ["under_threshold", "verdict_covered", "equipment_unambiguous", "no_possible_exclusion", "no_suspicious_signal", "low_commitment_action"] as const;
const short = (id?: string | null) => id?.slice(0, 8) ?? "—";
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
 const number = typeof payload.case_number === "string" ? payload.case_number : undefined;
 const screenshotUrl = typeof payload.screenshot_url === "string" ? payload.screenshot_url : undefined;
 const screenshotAlt = t("screenshotAlt");
 return <div className="mt-2 space-y-1 text-sm"><p>{typeof payload.text === "string" ? payload.text : "—"}</p>{number && <p className="font-semibold text-teal-900">{t("dellCase", { number })}</p>}{screenshotUrl && <><button type="button" aria-label={t("expandScreenshot")} className="block cursor-zoom-in" onClick={() => setExpanded(true)}><img src={screenshotUrl} alt={screenshotAlt} className="max-h-64 rounded border border-slate-200 object-contain"/></button><Dialog open={expanded} onOpenChange={setExpanded}><DialogContent className="max-w-5xl"><DialogTitle>{t("screenshot")}</DialogTitle><DialogDescription className="sr-only">{screenshotAlt}</DialogDescription><img src={screenshotUrl} alt={screenshotAlt} className="max-h-[80vh] w-full rounded object-contain"/></DialogContent></Dialog></>}</div>;
}
function ActionHistory({ history }: { history: CaseActionHistory }) {
 const { t } = useTranslation("caseDetail");
 return <li className="border-l-2 border-teal-600 pl-4"><div className="flex flex-wrap items-center gap-2"><h3 className="font-semibold">{t("enums:Channel." + history.action.channel)} · {history.action.kind}</h3><RealityBadge value={history.action.badge}/></div><ul className="mt-2 space-y-2 text-sm">{history.results.map((result, index) => { const number = proofCaseNumber(result.proof); return <li key={result.id ?? index}><p className={result.status === "success" ? "text-green-800" : "text-red-800"}>{t("result")} : {t("enums:ActionResultStatus." + result.status, { defaultValue: result.status })}</p>{number && <p className="font-semibold text-teal-900">{t("dellCase", { number })}</p>}{result.proof && <p className="break-all text-slate-600">{t("proofLabel")} : <code>{result.proof}</code></p>}{result.error && <p className="text-red-800">{t("payload.error")} : {result.error}</p>}</li>; })}</ul></li>;
}
function useFormat() {
 const { i18n } = useTranslation();
 return (at?: string | null) => at && !Number.isNaN(Date.parse(at)) ? new Date(at).toLocaleString(i18n.language) : "—";
}
function ErrorMessage({ error }: { error: unknown }) { const { t } = useTranslation(); return <p role="alert" className="py-3 text-red-800">{t(apiErrorKey(error))}</p>; }
function Evidence({ verdict }: { verdict?: Verdict | null }) {
 const { t } = useTranslation("caseDetail");
 return <div><h3 className="my-3 font-semibold">{t("evidence")}</h3>{!verdict?.evidence?.length ? <p className="text-sm text-slate-500">{t("none")}</p> : <ul className="space-y-3">{verdict.evidence.map((e, i) => <li key={e.id ?? i} className="border-l-2 border-teal-600 pl-3 text-sm"><p>{t("document")} <code title={e.document_id ?? undefined}>{short(e.document_id)}</code> · {t("page")} {e.page ?? "—"}</p><blockquote className="mt-1 text-slate-600">{e.excerpt}</blockquote></li>)}</ul>}</div>;
}
function Reasons({ item }: { item: Case }) {
 const { t } = useTranslation("caseDetail");
 return <ul className="my-3 text-sm text-slate-600">{item.policy?.reasons?.map(reason => <li key={reason}>{t("reasons." + reason, { defaultValue: reason.replaceAll("_", " ") })}</li>)}</ul>;
}
export function HumanActions({ item }: { item: Case }) {
 const { t } = useTranslation(["caseDetail", "common"]);
 const { personId } = useOperator();
 const action = useHumanAction(item.id ?? "");
 const [reject, setReject] = useState(false), [reason, setReason] = useState(""), [proof, setProof] = useState(""), [resolutionNote, setResolutionNote] = useState("");
 const disabled = !personId || action.isPending || !item.id;
 function submit(value: HumanAction) {
  if (disabled) return;
  action.mutate(value, { onSuccess: () => { toast.success(t("actionSuccess")); setReject(false); setReason(""); setProof(""); setResolutionNote(""); }, onError: error => toast.error(t(apiErrorKey(error))) });
 }
 return <div className="space-y-3">
 {!personId && <p className="text-sm text-amber-900">{t("common:identityRequired")}</p>}
 <div className="flex flex-wrap gap-2">
 {item.status === "awaiting_validation" && <><Button disabled={disabled} onClick={() => submit({ kind: "validate", person_id: personId })}>{t("validate")}</Button><Button variant="outline" disabled={disabled} onClick={() => setReject(true)}>{t("reject")}</Button></>}
 {item.status === "failed" && <Button disabled={disabled} onClick={() => submit({ kind: "manual-takeover", person_id: personId })}>{t("takeover")}</Button>}
 </div>
 {item.status === "manual_takeover" && <form className="space-y-2" onSubmit={e => { e.preventDefault(); if (proof.trim()) submit({ kind: "manual-proof", person_id: personId, proof: proof.trim() }); }}><label htmlFor={"proof-" + item.id}>{t("manualProof")}</label><Textarea id={"proof-" + item.id} value={proof} onChange={e => setProof(e.target.value)} required/><Button disabled={disabled || !proof.trim()}>{t("submitProof")}</Button></form>}
 {["sent", "tracked"].includes(item.status) && <form className="space-y-2" onSubmit={e => { e.preventDefault(); if (resolutionNote.trim()) submit({ kind: "resolve", person_id: personId, note: resolutionNote.trim() }); }}><label htmlFor={"resolution-note-" + item.id}>{t("resolutionNote")}</label><Textarea id={"resolution-note-" + item.id} value={resolutionNote} onChange={e => setResolutionNote(e.target.value)} required/><Button disabled={disabled || !resolutionNote.trim()}>{t("resolveCase")}</Button></form>}
 {action.isError && <ErrorMessage error={action.error}/>}
 <Dialog open={reject} onOpenChange={setReject}><DialogContent><DialogTitle>{t("reject")}</DialogTitle><DialogDescription>{t("reasonRequired")}</DialogDescription><form className="space-y-4" onSubmit={e => { e.preventDefault(); if (reason.trim()) submit({ kind: "reject", person_id: personId, reason: reason.trim() }); }}><label htmlFor={"reason-" + item.id}>{t("reason")}</label><Textarea id={"reason-" + item.id} value={reason} onChange={e => setReason(e.target.value)} required/><div className="flex gap-3"><Button disabled={disabled || !reason.trim()}>{t("confirmReject")}</Button><Button type="button" variant="outline" onClick={() => setReject(false)}>{t("common:cancel")}</Button></div></form></DialogContent></Dialog>
 </div>;
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
 const query = useCases();
 const [search, setSearch] = useState(""), [filters, setFilters] = useState<Record<string, string>>({}), [descending, setDescending] = useState(true);
 const rows = (query.data ?? []).filter(item => (item.id ?? "").toLowerCase().includes(search.toLowerCase()) && (!filters.status || item.status === filters.status) && (!filters.verdict || item.verdict?.value === filters.verdict) && (!filters.channel || item.channel === filters.channel) && (!filters.badge || item.badge === filters.badge)).sort((a, b) => ((Date.parse(b.updated_at ?? "") || 0) - (Date.parse(a.updated_at ?? "") || 0)) * (descending ? 1 : -1));
 const fields = { status: "CaseStatus", verdict: "VerdictValue", channel: "Channel", badge: "RealityBadge" };
 return <div className="space-y-5"><h1 className="text-3xl font-semibold">{t("title")}</h1><Card><div className="mb-5 grid gap-3 md:grid-cols-3"><label>{t("search")}<Input value={search} onChange={e => setSearch(e.target.value)}/></label>{Object.entries(fields).map(([key, ns]) => <label key={key}>{t(key)}<select className="block w-full rounded-md border border-slate-300 p-2" value={filters[key] ?? ""} onChange={e => setFilters({ ...filters, [key]: e.target.value })}><option value="">{t("all")}</option>{Array.from(new Set((query.data ?? []).map(item => key === "verdict" ? item.verdict?.value : item[key as "status" | "channel" | "badge"]))).filter((v): v is NonNullable<typeof v> => !!v).map(value => <option key={value} value={value}>{t("enums:" + ns + "." + value)}</option>)}</select></label>)}</div>
 {query.isPending && <p>{t("common:loading")}</p>}{query.isError && <ErrorMessage error={query.error}/>}
 <Table><thead><tr><th>{t("id")}</th><th>{t("status")}</th><th>{t("verdict")}</th><th>{t("channel")}</th><th>{t("badge")}</th><th aria-sort={descending ? "descending" : "ascending"}><button className="underline" onClick={() => setDescending(!descending)}>{t("updated")} {descending ? "↓" : "↑"}</button></th></tr></thead><tbody>{rows.map(item => <tr key={item.id} tabIndex={0} aria-label={item.id} className="cursor-pointer hover:bg-slate-50 focus-visible:outline-teal-700" onClick={() => navigate("/cases/" + item.id)} onKeyDown={event => { if (event.key === "Enter") navigate("/cases/" + item.id); }}><td><Link className="font-semibold text-teal-800 underline" to={"/cases/" + item.id}>{short(item.id)}</Link></td><td><StatusBadge value={item.status}/></td><td>{item.verdict ? <VerdictBadge value={item.verdict.value}/> : "—"}</td><td>{t("enums:Channel." + item.channel)}</td><td><RealityBadge value={item.badge}/></td><td>{date(item.updated_at)}</td></tr>)}</tbody></Table>{!query.isPending && !query.isError && !rows.length && <p className="p-5 text-slate-600">{t("empty")}</p>}</Card></div>;
}
function Checklist({ id }: { id: string }) {
 const { t } = useTranslation("caseDetail"), date = useFormat();
 const query = useChecklist(id), action = useHumanAction(id), { personId } = useOperator();
 if (query.error instanceof ApiError && query.error.status === 404) return null;
 return <Card><h2 className="mb-4 text-xl font-semibold">{t("checklist")}</h2>{query.isPending && <p>{t("common:loading")}</p>}{query.isError && <ErrorMessage error={query.error}/>}
 {!personId && <p className="mb-4 text-sm text-amber-900">{t("common:identityRequired")}</p>}
 {query.data && <ol className="space-y-5">{steps.map((step, index) => { const data = query.data.steps?.[step]; return <li key={step} className="border-b border-slate-100 pb-4"><h3 className="font-semibold">{index + 1}. {t("enums:ChecklistStepName." + step)} {data?.done ? "✓" : ""}</h3><p className="my-1 text-sm text-slate-600">{t("steps." + step)}</p><p className="text-sm">{t("who")}: {t(["repair_type", "shipping_label"].includes(step) ? "agent" : "human")}</p>{data?.done ? <p className="mt-2 text-sm">{data.by_person_id ?? "—"} · {date(data.at)}</p> : <Button className="mt-2" variant="outline" disabled={!personId || action.isPending} onClick={() => action.mutate({ kind: "checklist", step, person_id: personId }, { onSuccess: () => toast.success(t("actionSuccess")), onError: error => toast.error(t(apiErrorKey(error))) })}>{t("complete")}</Button>}</li>; })}</ol>}{action.isError && <ErrorMessage error={action.error}/>}</Card>;
}
function Payload({ payload }: { payload: Record<string, unknown> }) {
 const { t } = useTranslation("caseDetail");
 function readable(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (Array.isArray(value)) return value.map(readable).join(" · ");
  if (typeof value === "object") return Object.entries(value).map(([key, child]) => t("payload." + key, { defaultValue: key.replaceAll("_", " ") }) + ": " + readable(child)).join(" · ");
  return String(value);
 }
 return <dl className="mt-2 space-y-1 break-words text-sm text-slate-600">{Object.entries(payload).map(([key, value]) => <div key={key}><dt className="inline font-medium">{t("payload." + key, { defaultValue: key.replaceAll("_", " ") })}: </dt><dd className="inline">{key === "badge" && (value === "real" || value === "reproduction" || value === "simulated") ? <RealityBadge value={value}/> : key === "from" || key === "to" ? t("enums:CaseStatus." + String(value), { defaultValue: readable(value) }) : key === "step" ? t("enums:ChecklistStepName." + String(value), { defaultValue: readable(value) }) : readable(value)}</dd></div>)}</dl>;
}
function EventRow({ event }: { event: StreamEventLocal }) {
 const { t } = useTranslation("caseDetail"), date = useFormat();
 const actor = event.actor.startsWith("human:") ? t("human") + " · " + event.actor.slice(6) : t(event.actor, { defaultValue: event.actor });
 return <li className="border-l-2 border-teal-600 pl-4"><h3 className="font-semibold">{t("enums:EventType." + event.type, { defaultValue: event.type })}</h3><p className="text-xs text-slate-500">{date(event.at)} · {actor} · #{event.seq}</p>{event.type === "action_step" ? <BrowserStep payload={event.payload}/> : <Payload payload={event.payload}/>}</li>;
}
export function CaseDetail() {
 const { id = "" } = useParams(), { t, i18n } = useTranslation("caseDetail"), date = useFormat();
 const query = useCase(id), stream = useCaseStream(id), history = useCaseActions(id), equipmentName = useEquipmentName();
 const item = query.data, verdict = item?.verdict;
 if (query.isPending) return <p>{t("common:loading")}</p>;
 if (query.isError) return <ErrorMessage error={query.error}/>;
 if (!item) return null;
 return <div className="space-y-6"><Link className="text-teal-800 underline" to="/cases">{t("back")}</Link><header className="space-y-3"><h1 className="text-3xl font-semibold">{t("title")} #{short(item.id)}</h1><div className="flex flex-wrap gap-3"><StatusBadge value={item.status}/><RealityBadge value={item.badge}/><span>{t("enums:Channel." + (verdict?.channel ?? item.channel))}</span><span>{t("equipmentLabel")} : {equipmentName(item.equipment_id)}</span></div><p className="text-sm text-slate-600">{t("created")}: {date(item.created_at)} · {t("updated")}: {date(item.updated_at)}</p><HumanActions item={item}/></header>
 <div className="grid items-start gap-6 xl:grid-cols-2"><Card><h2 className="mb-4 text-xl font-semibold">{t("verdict")}</h2>{verdict ? <><VerdictBadge value={verdict.value}/><p className="my-3">{i18n.language.startsWith("fr") ? verdict.explanation_fr : verdict.explanation_en}</p><p className="text-sm">{t("rule")}: {verdict.rule_id ?? "—"} · {t("version", { version: verdict.rule_version ?? "—" })}</p><ul className="my-4 space-y-3">{verdict.checks?.map((check, index) => <li key={check.id ?? index}><span className={check.passed === true ? "text-green-800" : check.passed === false ? "text-red-800" : "text-slate-600"}>{check.passed === true ? "✓" : check.passed === false ? "✗" : t("undetermined")}</span> {t("checkNames." + check.name, { defaultValue: check.name })}<p className="text-sm text-slate-600">{t("checkDetails." + check.name, { defaultValue: check.detail })}</p></li>)}</ul><h3 className="font-semibold">{t("missing")}</h3><p>{verdict.missing?.join(" · ") || t("none")}</p><h3 className="mt-3 font-semibold">{t("exclusions")}</h3><p>{verdict.possible_exclusions?.join(" · ") || t("none")}</p><Evidence verdict={verdict}/></> : <p>{t("none")}</p>}</Card>
 <Card><h2 className="mb-4 text-xl font-semibold">{t("policy")}</h2>{item.policy ? <><p className="font-semibold">{t("enums:PolicyOutcome." + item.policy.outcome)}</p><Reasons item={item}/><ul className="space-y-3">{conditions.map(key => <li key={key}><span className={item.policy!.conditions[key] ? "text-green-800" : "text-red-800"}>{item.policy!.conditions[key] === true ? "✓" : item.policy!.conditions[key] === false ? "✗" : t("undetermined")}</span> {t("conditions." + key)}</li>)}</ul></> : <p>{t("none")}</p>}</Card></div>
 <Checklist id={id}/>
 <Card><h2 className="text-xl font-semibold">{t("actions")}</h2><p className="my-3 text-sm text-slate-600">{t("actionsNote")}</p>{history.isError && <ErrorMessage error={history.error}/>}{history.data && !history.data.length && <p>{t("none")}</p>}<ol className="space-y-5">{history.data?.map((entry, index) => <ActionHistory key={entry.action.id ?? index} history={entry}/>)}</ol></Card>
 <Card><div className="mb-5 flex flex-wrap justify-between gap-3"><h2 className="text-xl font-semibold">{t("timeline")}</h2><span role="status" className={stream.connection === "open" ? "text-green-800" : "text-amber-900"}>{t(stream.mode === "poll" ? "polling" : stream.connection === "open" ? "liveSse" : "reconnecting")}</span></div>{stream.isError && <ErrorMessage error={stream.error}/>}<ol className="space-y-6">{stream.data?.map(e => <EventRow key={e.seq} event={e}/>)}</ol>{!stream.isPending && !stream.data?.length && <p>{t("none")}</p>}</Card></div>;
}
