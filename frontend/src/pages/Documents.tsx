import { useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { ApiError, client, localRequest, unwrap } from "@/api/client";
import { apiErrorKey } from "@/api/errors";
import type { components } from "@/api/schema";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

type UploadResult = { document_id: string; duplicate: boolean; reason?: string; state?: string; facts?: number };
type PollState = "failure" | "invoice" | "duplicate" | "quarantined" | "ignored";
const pollStates: PollState[] = ["failure", "invoice", "duplicate", "quarantined", "ignored"];
const limit = 20;

export default function Documents() {
 const { t, i18n } = useTranslation("documents");
 const cache = useQueryClient();
 const input = useRef<HTMLInputElement>(null);
 const [offset, setOffset] = useState(0), [busy, setBusy] = useState<"upload" | "poll">();
 const [error, setError] = useState<unknown>(), [validation, setValidation] = useState<string>();
 const [result, setResult] = useState<UploadResult>(), [detail, setDetail] = useState<components["schemas"]["DocumentDetail"]>();
 const [summary, setSummary] = useState<Record<PollState, number>>();
 const query = useQuery({
  queryKey: ["documents", offset],
  queryFn: async () => unwrap(await client.GET("/api/documents", { params: { query: { limit, offset } } })),
 });
 async function refresh() { await cache.invalidateQueries({ queryKey: ["documents"] }); }
 async function upload(file?: File) {
  if (!file || busy) return;
  setValidation(undefined); setError(undefined); setResult(undefined); setDetail(undefined);
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
  setBusy("poll"); setError(undefined); setValidation(undefined);
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
 return <div className="space-y-5">
  <h1 className="text-3xl font-semibold">{t("title")}</h1>
  <Card className="space-y-4">
   <h2 className="text-xl font-semibold">{t("uploadTitle")}</h2>
   <button type="button" disabled={!!busy} onClick={() => input.current?.click()} onDragOver={event => event.preventDefault()} onDrop={event => { event.preventDefault(); if (!busy) void upload(event.dataTransfer.files[0]); }} className="w-full rounded-lg border-2 border-dashed border-teal-600 bg-teal-50 p-8 text-center text-teal-950 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-700 disabled:opacity-50">
    {t("drop")}
   </button>
   <p className="text-sm text-slate-600" id="document-formats">{t("formats")}</p>
   <label className="block font-medium" htmlFor="document-file">{t("choose")}</label>
   <input ref={input} id="document-file" type="file" accept=".pdf,.xml" aria-describedby="document-formats" disabled={!!busy} className="block w-full rounded border border-slate-300 p-2 file:mr-4 file:rounded file:border-0 file:bg-teal-800 file:px-4 file:py-2 file:text-white" onChange={event => { void upload(event.target.files?.[0]); event.target.value = ""; }}/>
   {busy && <p role="status" aria-live="polite" aria-busy="true">{t(busy === "upload" ? "uploading" : "polling")}</p>}
   {validation && <p role="alert" className="text-red-800">{t(validation)}</p>}
   {error !== undefined && <p role="alert" className="text-red-800">{errorText(error)}</p>}
  </Card>
  {result && <Card className="space-y-3"><h2 className="text-xl font-semibold">{t("resultTitle")}</h2><div role="status" aria-live="polite">
   {result.duplicate ? <p>{t("duplicate", { reason: t("reasons." + result.reason, { defaultValue: result.reason ?? t("unknownReason") }) })}</p> : <p>{t("results." + result.state, { count: result.facts ?? 0 })}</p>}
   {detail?.suspicious && result.duplicate && <p>{t("results.quarantined")}</p>}
  </div>
  {!!detail?.facts.length && <details><summary className="cursor-pointer font-semibold">{t("factsTitle")}</summary><dl className="mt-3 space-y-2">{detail.facts.map((fact, index) => <div key={index} className="rounded bg-slate-50 p-3"><dt className="font-medium">{fact.field}</dt><dd className="break-words">{typeof fact.value === "string" ? fact.value : JSON.stringify(fact.value)}</dd><dd className="text-sm text-slate-600">{t("confidence", { value: new Intl.NumberFormat(i18n.language, { style: "percent" }).format(fact.confidence) })}</dd></div>)}</dl></details>}
  </Card>}
  <Card className="space-y-4"><h2 className="text-xl font-semibold">{t("inboxTitle")}</h2><Button disabled={!!busy} onClick={() => void poll()}>{t("poll")}</Button>
   {summary && <div role="status" aria-live="polite"><h3 className="font-semibold">{t("summary")}</h3><ul className="mt-2 flex flex-wrap gap-x-6 gap-y-2">{pollStates.map(state => <li key={state}>{t("pollStates." + state, { count: summary[state] })}</li>)}</ul></div>}
  </Card>
  <Card className="space-y-4"><h2 className="text-xl font-semibold">{t("listTitle")}</h2>
   {query.isPending && <p role="status">{t("common:loading")}</p>}
   {query.isError && <p role="alert">{errorText(query.error)}</p>}
   {query.data && <><p>{t("total", { count: query.data.total })}</p><div className="overflow-x-auto"><table className="w-full text-left text-sm"><caption className="sr-only">{t("listTitle")}</caption><thead><tr>{["name", "source", "state", "suspicious", "facts", "date"].map(column => <th key={column} scope="col" className="border-b p-3">{t("columns." + column)}</th>)}</tr></thead><tbody>{query.data.items.map(item => <tr key={item.id}><td className="border-b p-3 font-medium">{item.name}</td><td className="border-b p-3">{t("enums:DocumentSource." + item.source)}</td><td className="border-b p-3">{t("states." + item.state)}</td><td className="border-b p-3">{t(item.suspicious ? "yes" : "no")}</td><td className="border-b p-3">{item.facts_count}</td><td className="whitespace-nowrap border-b p-3">{date(item.created_at)}</td></tr>)}</tbody></table></div>
   {query.data.items.length === 0 && <p>{t("empty")}</p>}
   <nav aria-label={t("pagination")} className="flex items-center gap-3"><Button variant="outline" disabled={offset === 0 || query.isFetching} onClick={() => setOffset(Math.max(0, offset - limit))}>{t("previous")}</Button><p>{t("page", { number: Math.floor(offset / limit) + 1 })}</p><Button variant="outline" disabled={offset + limit >= query.data.total || query.isFetching} onClick={() => setOffset(offset + limit)}>{t("next")}</Button></nav></>}
  </Card>
 </div>;
}
