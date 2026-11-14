import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { FileCode, FileText, UploadCloud } from "lucide-react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { ApiError, client, localRequest, unwrap } from "@/api/client";
import { apiErrorKey } from "@/api/errors";
import type { components } from "@/api/schema";
import { Button } from "@/components/ui/button";
import { Tile as Card } from "@/components/bento/Tile";
import { EmptyState } from "@/components/bento/EmptyState";
import { Pill } from "@/components/bento/Pill";
import { StatusDot } from "@/components/bento/StatusDot";
import { UploadProgress } from "@/components/documents/UploadProgress";
import { isTechnicalValue, technicalLabel } from "@/i18n/technical";

type UploadResult = { document_id: string; duplicate: boolean; reason?: string; state?: string; facts?: number; suspicious?: boolean };
type PollState = "failure" | "invoice" | "duplicate" | "quarantined" | "ignored";
const pollStates: PollState[] = ["failure", "invoice", "duplicate", "quarantined", "ignored"];
const limit = 20;

export default function Documents() {
 const { t, i18n } = useTranslation("documents");
 const cache = useQueryClient();
 const input = useRef<HTMLInputElement>(null);
 const [params] = useSearchParams();
 const documentId = params.get("document");
 const linked = useQuery({ queryKey: ["document", documentId], enabled: !!documentId, retry: false, queryFn: async () => unwrap(await client.GET("/api/documents/{document_id}", { params: { path: { document_id: documentId! } } })) });
 const selected = useRef<HTMLElement>(null);
 const [filename, setFilename] = useState<string>();
 const [offset, setOffset] = useState(0), [busy, setBusy] = useState<"upload" | "poll">();
 const [error, setError] = useState<unknown>(), [validation, setValidation] = useState<string>();
 const [errorSource, setErrorSource] = useState<"upload" | "poll">("upload");
 const [result, setResult] = useState<UploadResult>(), [detail, setDetail] = useState<components["schemas"]["DocumentDetail"]>();
 const [summary, setSummary] = useState<Record<PollState, number>>();
 const query = useQuery({
  queryKey: ["documents", offset],
  queryFn: async () => unwrap(await client.GET("/api/documents", { params: { query: { limit, offset } } })),
 });
 useEffect(() => { if (linked.data) selected.current?.scrollIntoView?.({ block: "nearest" }); }, [linked.data, query.data]);
 async function refresh() { await cache.invalidateQueries({ queryKey: ["documents"] }); }
 async function upload(file?: File) {
  if (!file || busy) return;
  setValidation(undefined); setError(undefined); setErrorSource("upload"); setResult(undefined); setDetail(undefined); setFilename(file.name);
  if (!/\.(pdf|xml)$/i.test(file.name)) { setValidation("invalidType"); return; }
  if (file.size > 10 * 1024 * 1024) { setValidation("tooLarge"); return; }
  setBusy("upload");
  try {
   const form = new FormData(); form.append("file", file);
   const uploaded = await unwrap(await client.POST("/api/documents/upload", {
    body: { file: file.name }, bodySerializer: () => form,
   })) as UploadResult;
   setResult(uploaded);
   await refresh();
   setDetail(await unwrap(await client.GET("/api/documents/{document_id}", { params: { path: { document_id: uploaded.document_id } } })));
  } catch (reason) { setError(reason ?? true); } finally { setBusy(undefined); }
 }
 async function poll() {
  if (busy) return;
  setBusy("poll"); setError(undefined); setErrorSource("poll"); setValidation(undefined);
  try {
   const response = await localRequest<{ messages: { state: string }[] }>("/intake/poll", "POST");
   const counts = Object.fromEntries(pollStates.map(state => [state, response.messages.filter(message => message.state === state).length])) as Record<PollState, number>;
   setSummary(counts); await refresh();
  } catch (reason) { setError(reason ?? true); } finally { setBusy(undefined); }
 }
 function errorText(reason: unknown) {
  if (reason instanceof ApiError && [400, 413, 415].includes(reason.status)) {
   let detail: unknown = reason.detail;
   if (typeof detail === "string") { try { detail = JSON.parse(detail) as unknown; } catch { /* Plain server detail. */ } }
   if (detail && typeof detail === "object" && "detail" in detail) detail = detail.detail;
   if (typeof detail === "string") return t("serverError", { detail });
  }
  return t(apiErrorKey(reason));
 }
 const date = (at: string | null) => at ? new Intl.DateTimeFormat(i18n.language, { dateStyle: "short", timeStyle: "short" }).format(new Date(at)) : "—";
 function documentTile(item: components["schemas"]["DocumentItem"]) {
  const active = item.id === documentId;
  const Icon = /\.xml$/i.test(item.name) ? FileCode : FileText;
  return <Card key={item.id} ref={active ? selected : undefined} highlight={active} className="min-w-0 space-y-4" aria-label={item.name}>
   <span className="inline-flex rounded-2xl bg-accent/10 p-3"><Icon size={36} strokeWidth={1.75} aria-hidden="true"/></span>
   <h3 className="break-all font-semibold">{item.name}</h3>
   <div className="flex flex-wrap gap-2"><Pill className={`gap-2 ${item.state === "extracted" ? "bg-ok/15" : item.state === "quarantined" ? "bg-bad/15" : "bg-warn/20"}`}><StatusDot tone={item.state === "extracted" ? "ok" : item.state === "quarantined" ? "bad" : "waiting"}/>{t("states." + item.state)}</Pill>{item.suspicious && <Pill className="gap-2 bg-bad/15"><StatusDot tone="bad"/>{t("columns.suspicious")}</Pill>}</div>
   <dl className="grid grid-cols-2 gap-3 text-sm">{[
    ["source", t("enums:DocumentSource." + item.source)],
    ["suspicious", t(item.suspicious ? "yes" : "no")], ["facts", item.facts_count], ["date", date(item.created_at)],
   ].map(([label, value]) => <div key={label} className="min-w-0"><dt className="text-muted">{t("columns." + label)}</dt><dd className="break-words">{value}</dd></div>)}</dl>
   {active && linked.data && <details open><summary className="min-h-10 cursor-pointer font-medium focus-visible:outline-accent">{t("factsTitle")}</summary><dl className="space-y-3">{linked.data.facts.map((fact, index) => <div key={index} className="[overflow-wrap:anywhere]"><dt className="text-sm text-muted">{technicalLabel(fact.field, i18n.language)}</dt><dd>{typeof fact.value === "string" ? fact.value : JSON.stringify(fact.value)}</dd></div>)}</dl></details>}
  </Card>;
 }
 return <div className="space-y-5 text-ink">
  <h1 className="text-4xl font-bold tracking-tight">{t("title")}</h1>
  <Card className="space-y-4">
   <h2 className="text-xl font-semibold">{t("uploadTitle")}</h2>
   <label htmlFor="document-file" role="button" tabIndex={busy ? -1 : 0} aria-label={t("drop")} aria-describedby="document-formats" aria-disabled={!!busy} onClick={event => { if (busy) event.preventDefault(); }} onKeyDown={event => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); if (!busy) input.current?.click(); } }} onDragOver={event => event.preventDefault()} onDrop={event => { event.preventDefault(); if (!busy) void upload(event.dataTransfer.files[0]); }} className="flex min-h-48 w-full cursor-pointer flex-col items-center justify-center gap-4 rounded-[28px] border-2 border-dashed border-idle bg-canvas p-6 text-center font-medium focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent aria-disabled:cursor-not-allowed aria-disabled:opacity-50">
    <UploadCloud size={40} strokeWidth={1.75} aria-hidden="true"/>{t("drop")}
    <input ref={input} id="document-file" type="file" accept=".pdf,.xml" aria-label={t("choose")} aria-describedby="document-formats" tabIndex={-1} disabled={!!busy} className="sr-only" onChange={event => { void upload(event.target.files?.[0]); event.target.value = ""; }}/>
   </label>
   <p className="text-sm text-slate-600" id="document-formats">{t("formats")}</p>
   {filename && <UploadProgress name={filename} waiting={busy === "upload"} state={result?.state} duplicate={result?.duplicate} documentId={result?.document_id} suspicious={result?.suspicious || detail?.suspicious} reason={result?.reason} facts={result?.facts} error={validation ? t(validation) : error !== undefined && errorSource === "upload" ? errorText(error) : undefined}>
   {result?.state === "pending_extraction" && <p role="status">{t("results.pending_extraction")}</p>}
  {!!detail?.facts.length && <details><summary className="cursor-pointer font-semibold">{t("factsTitle")}</summary><dl className="mt-3 space-y-2">{detail.facts.map((fact, index) => { const value = typeof fact.value === "string" ? fact.value : JSON.stringify(fact.value); const technical = isTechnicalValue(value) || typeof fact.value === "object" && fact.value !== null; return <div key={index} className="rounded bg-slate-50 p-3"><dt className="font-medium [overflow-wrap:anywhere]">{technicalLabel(fact.field, i18n.language)}</dt>{technical ? <dd><details className="mt-1"><summary className="cursor-pointer text-sm text-slate-600">{t("technicalDetails")}</summary><pre className="mt-2 max-w-full overflow-x-auto whitespace-pre rounded bg-white p-3 text-xs">{value}</pre></details></dd> : <dd className="[overflow-wrap:anywhere]">{value}</dd>}<dd className="text-sm text-slate-600">{t("confidence", { value: new Intl.NumberFormat(i18n.language, { style: "percent" }).format(fact.confidence) })}</dd></div>; })}</dl></details>}
   </UploadProgress>}
  </Card>
  <Card className="space-y-4"><h2 className="text-xl font-semibold">{t("inboxTitle")}</h2><Button disabled={!!busy} onClick={() => void poll()}>{t("poll")}</Button>
   {busy === "poll" && <p role="status" aria-live="polite" aria-busy="true">{t("polling")}</p>}
   {error !== undefined && errorSource === "poll" && <p role="alert" className="text-red-800">{errorText(error)}</p>}
   {summary && <div role="status" aria-live="polite"><h3 className="font-semibold">{t("summary")}</h3><ul className="mt-2 flex flex-wrap gap-x-6 gap-y-2">{pollStates.map(state => <li key={state}>{t("pollStates." + state, { count: summary[state] })}</li>)}</ul></div>}
  </Card>
  <section className="space-y-4" aria-label={t("listTitle")}><h2 className="text-xl font-semibold">{t("listTitle")}</h2>
   {query.isPending && <p role="status">{t("common:loading")}</p>}
   {query.isError && <p role="alert">{errorText(query.error)}</p>}
   {linked.isError && <p role="status" className="text-sm text-muted">{t("documentUnavailable")}</p>}
   {query.data && <><p>{t("total", { count: query.data.total })}</p><div className="grid min-w-0 grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">{linked.data && !query.data.items.some(item => item.id === linked.data.id) && documentTile(linked.data)}{query.data.items.map(documentTile)}</div>
   {query.data.items.length === 0 && <EmptyState title={t("empty")}/>}
   <nav aria-label={t("pagination")} className="flex items-center gap-3"><Button variant="outline" disabled={offset === 0 || query.isFetching} onClick={() => setOffset(Math.max(0, offset - limit))}>{t("previous")}</Button><p>{t("page", { number: Math.floor(offset / limit) + 1 })}</p><Button variant="outline" disabled={offset + limit >= query.data.total || query.isFetching} onClick={() => setOffset(offset + limit)}>{t("next")}</Button></nav></>}
  </section>
 </div>;
}
