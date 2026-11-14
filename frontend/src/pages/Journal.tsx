import { useState } from "react";
import { Link } from "react-router-dom";
import { useQueries } from "@tanstack/react-query";
import { motion, useReducedMotion } from "motion/react";
import { Activity, Anchor, CheckCheck, ChevronDown, CircleAlert, FileText, MessageSquare, Pause, Play, Settings, ShieldCheck, ShoppingBag } from "lucide-react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { useJournal, useAnchorJournal, useCases } from "@/api/hooks";
import { usePeople } from "@/api/resources";
import { client, unwrap } from "@/api/client";
import { apiErrorKey } from "@/api/errors";
import { technicalLabel } from "@/i18n/technical";
import { Tile } from "@/components/bento/Tile";
import { StatusDot } from "@/components/bento/StatusDot";
import { Pill } from "@/components/bento/Pill";
import { EmptyState } from "@/components/bento/EmptyState";
import { Button } from "@/components/ui/button";

function eventIcon(type: string) {
 if (type.startsWith("purchase_guard")) return ShoppingBag;
 if (type.includes("failed") || type === "rejected") return CircleAlert;
 if (type === "agent_paused") return Pause;
 if (type === "agent_resumed") return Play;
 if (type === "settings_changed") return Settings;
 if (type === "journal_anchored") return Anchor;
 if (type.includes("fact") || type.includes("document") || type === "case_created") return FileText;
 if (type.includes("message") || type.includes("followup") || type.includes("reminder") || type === "chat_disclosure") return MessageSquare;
 if (type.includes("validat") || type.includes("verdict") || type.includes("policy") || type.includes("checklist") || type === "action_succeeded") return CheckCheck;
 return Activity;
}

function CaseEvents() {
 const { t, i18n } = useTranslation("journal"), cases = useCases(), people = usePeople();
 const [visible, setVisible] = useState(10);
 const reduced = useReducedMotion();
 const recent = (Array.isArray(cases.data) ? cases.data : []).filter(item => !!item.id).sort((a, b) => Date.parse(b.updated_at ?? b.created_at ?? "1970-01-01") - Date.parse(a.updated_at ?? a.created_at ?? "1970-01-01")).slice(0, 20);
 const queries = useQueries({ queries: recent.map(item => ({
  queryKey: ["journal-case-events", item.id],
  queryFn: async () => unwrap(await client.GET("/api/cases/{case_id}/events", { params: { path: { case_id: item.id! } } })),
  refetchInterval: 10000,
 })) });
 const events = queries.flatMap((query, index) => (query.data ?? []).map(event => ({ ...event, caseId: recent[index].id! }))).sort((a, b) => Date.parse(b.at ?? "1970-01-01") - Date.parse(a.at ?? "1970-01-01") || b.seq - a.seq);
 const loading = cases.isPending || queries.some(query => query.isPending);
 const error = cases.error ?? queries.find(query => query.isError)?.error;
 const payloadLabel = (key: string) => t("payloadLabels." + key, { defaultValue: technicalLabel(key, i18n.language) });
 function readable(value: unknown, key = ""): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "boolean") return t(value ? "yes" : "no");
  if (Array.isArray(value)) return value.map(entry => readable(entry, key)).join(" · ");
  if (typeof value === "object") return Object.entries(value).map(([nestedKey, entry]) => `${payloadLabel(nestedKey)} : ${readable(entry, nestedKey)}`).join(" · ");
  if (typeof value === "string" && key === "reasons") return t("caseDetail:reasons." + value, { defaultValue: t("reasonLabels." + value, { defaultValue: technicalLabel(value, i18n.language) }) });
  const enumName = ({ from: "CaseStatus", to: "CaseStatus", channel: "Channel", outcome: "PolicyOutcome", verdict: "VerdictValue", badge: "RealityBadge", step: "ChecklistStepName" } as Record<string, string>)[key];
  if (typeof value === "string" && enumName) return t(`enums:${enumName}.${value}`, { defaultValue: technicalLabel(value, i18n.language) });
  return typeof value === "string" && /^[a-z]+(?:_[a-z]+)+$/.test(value) ? technicalLabel(value, i18n.language) : String(value);
 }
 return <section className="space-y-5" aria-labelledby="journal-events-title">
  <div className="space-y-2"><h2 id="journal-events-title" className="text-2xl font-bold tracking-tight">{t("eventsTitle")}</h2><p className="max-w-3xl text-sm text-ink">{t("eventsScope", { count: 20 })}</p></div>
  {loading && <p aria-live="polite">{t("common:loading")}</p>}
  {error && <Tile><p role="alert">{t(apiErrorKey(error))}</p><p className="mt-2 text-sm">{t("partial")}</p></Tile>}
  {!loading && !error && events.length === 0 && <Tile><EmptyState title={t("empty")} icon={<Activity size={32}/>}/></Tile>}
  <ol className="relative space-y-4 border-l-2 border-line pl-5 sm:pl-8">
   {events.slice(0, visible).map(event => {
    const Icon = eventIcon(event.type);
    const actor = event.actor.startsWith("human:") ? (people.data?.find(person => person.id === event.actor.slice(6))?.name ?? t("human")) : t(event.actor === "agent" ? "agent" : "system");
    const label = t("enums:EventType." + event.type, { defaultValue: t("eventLabels." + event.type, { defaultValue: technicalLabel(event.type, i18n.language) }) });
    return <motion.li key={`${event.caseId}-${event.seq}`} className="relative min-w-0" initial={reduced ? false : { opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: reduced ? 0 : 0.25 }}>
     <span className="absolute -left-[27px] top-7 rounded-full bg-canvas sm:-left-10"><StatusDot tone={event.type === "action_failed" || event.type === "rejected" ? "bad" : "idle"}/></span>
     <Tile className="min-w-0 space-y-3">
      <div className="flex items-start gap-3"><span className="shrink-0 rounded-2xl bg-canvas p-3"><Icon size={24} strokeWidth={1.75} aria-hidden="true"/></span><div className="min-w-0 flex-1"><h3 className="text-lg font-semibold [overflow-wrap:anywhere]">{label}</h3><p className="text-sm text-ink">{actor}</p></div></div>
      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 text-sm"><time dateTime={event.at}>{event.at ? new Intl.DateTimeFormat(i18n.language, { dateStyle: "medium", timeStyle: "short" }).format(new Date(event.at)) : t("unknownDate")}</time><Link className="inline-flex min-h-10 items-center rounded-full font-semibold underline underline-offset-4 focus-visible:outline-2 focus-visible:outline-accent" to={"/cases/" + event.caseId}>{t("caseReference", { id: event.caseId.slice(0, 8) })}</Link></div>
      <details className="group"><summary className="flex min-h-10 cursor-pointer items-center gap-2 rounded-xl font-medium underline decoration-line underline-offset-4 focus-visible:outline-2 focus-visible:outline-accent">{t("details")}<ChevronDown size={16} className="group-open:rotate-180" aria-hidden="true"/></summary>{Object.keys(event.payload ?? {}).length ? <dl className="space-y-3 rounded-2xl bg-canvas p-4 text-sm [overflow-wrap:anywhere]">{Object.entries(event.payload ?? {}).map(([key, value]) => <div key={key}><dt className="font-semibold">{payloadLabel(key)}</dt><dd>{readable(value, key)}</dd></div>)}</dl> : <p className="text-sm">{t("noDetails")}</p>}</details>
     </Tile>
    </motion.li>;
   })}
  </ol>
  {visible < events.length && <Button variant="outline" onClick={() => setVisible(value => value + 10)}>{t("showMore")}</Button>}
 </section>;
}

export default function Journal() {
 const { t } = useTranslation("journal"), query = useJournal(), anchor = useAnchorJournal();
 return <div className="space-y-8 text-ink"><h1 className="text-4xl font-bold tracking-tight">{t("title")}</h1><Tile className="space-y-5" aria-label={t("integrity")}>
  <div className="flex items-center gap-3"><span className="rounded-2xl bg-canvas p-3"><ShieldCheck size={28} strokeWidth={1.75} aria-hidden="true"/></span><h2 className="text-lg font-semibold">{t("integrity")}</h2></div>
  {query.isPending && <p>{t("common:loading")}</p>}{query.isError && <p role="alert">{t(apiErrorKey(query.error))}</p>}
  {query.data && <><div role="status" className="flex items-start gap-3"><span className="mt-2"><StatusDot tone={query.data.ok ? "ok" : "bad"}/></span><p className="text-2xl font-bold tracking-tight sm:text-3xl">{query.data.ok ? t("intact") : query.data.first_bad_seq !== null ? t("modified", { seq: query.data.first_bad_seq }) : t("invalid")}</p></div><div className="flex flex-wrap gap-3"><Pill className="bg-canvas text-sm">{t("checked", { count: query.data.checked })}</Pill><Pill className={query.data.anchors_ok ? "bg-ok/15" : "bg-bad/15"}>{t(query.data.anchors_ok ? "anchorsOk" : "anchorsKo")}</Pill></div></>}
  <Button disabled={anchor.isPending} onClick={() => anchor.mutate(undefined, { onSuccess: () => toast.success(t("anchored")), onError: error => toast.error(t(apiErrorKey(error))) })}><Anchor size={16} aria-hidden="true"/>{t("anchor")}</Button>{anchor.isError && <p role="alert">{t(apiErrorKey(anchor.error))}</p>}
 </Tile>{query.data && <CaseEvents/>}</div>;
}
