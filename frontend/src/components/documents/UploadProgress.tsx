import { motion, useReducedMotion } from "motion/react";
import type { ReactNode } from "react";
import { Check, FileText, AlertTriangle } from "lucide-react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Pill } from "@/components/bento/Pill";
import { StatusDot } from "@/components/bento/StatusDot";

export function UploadProgress({ name, waiting, state, duplicate, documentId, suspicious, reason, facts, error, children }: { name: string; waiting: boolean; state?: string; duplicate?: boolean; documentId?: string; suspicious?: boolean; reason?: string; facts?: number; error?: string; children?: ReactNode }) {
 const { t } = useTranslation("documents");
 const reduced = useReducedMotion();
 const verified = !!state && !duplicate;
 const read = state === "extracted";
 const suspect = suspicious || state === "quarantined" || !!reason && !duplicate;
 return <div data-testid="upload-card" className="min-w-0 space-y-5 rounded-[28px] bg-canvas p-5 sm:p-6">
  <div className="flex items-center gap-3"><span className="rounded-2xl bg-accent/10 p-3"><FileText aria-hidden="true" className="shrink-0"/></span><p className="min-w-0 break-all text-lg font-semibold">{name}</p></div>
  <ol className="grid grid-cols-3" aria-label={t("stepsTitle")}>
   {([ ["sent", !!state || !!duplicate], ["verified", verified], ["read", read] ] as const).map(([step, complete], index) => {
    const current = waiting && index === 0 && !complete;
    return <li key={step} aria-current={current ? "step" : undefined} className="relative flex min-w-0 flex-col items-center gap-3 text-center text-sm font-medium sm:text-base">
     {index < 2 && <span aria-hidden="true" className={`absolute left-1/2 top-5 h-0.5 w-full ${complete ? "bg-ok" : "bg-idle"}`}/>}
     <span className={`relative flex h-10 w-10 items-center justify-center rounded-full border-2 ${complete ? "border-ok bg-ok" : current ? "border-accent bg-surface" : "border-idle bg-canvas"}`}>
      {complete ? <Check size={22} strokeWidth={2.5} className="text-ink" aria-label={t("completed")}/> : <StatusDot tone={current ? "active" : "idle"}/>}
     </span><span>{t("steps." + step)}</span>
    </li>;
   })}
  </ol>
  {waiting && <><p role="status" aria-live="polite" aria-busy="true">{t("uploading")}</p><div role="progressbar" aria-label={t("uploading")} className="h-1.5 overflow-hidden rounded-full bg-line"><motion.div className="h-full w-1/3 rounded-full bg-accent" initial={false} animate={reduced ? { x: 0 } : { x: ["-100%", "300%"] }} transition={reduced ? { duration: 0 } : { duration: 1.4, repeat: Infinity, ease: "linear" }}/></div></>}
  <div role="status" aria-live="polite" className="flex flex-wrap items-center gap-3">
   {duplicate && <><Pill className="gap-2 bg-warn/20"><StatusDot tone="waiting"/>{t("duplicateBadge")}</Pill>{documentId && <Link to={`?document=${encodeURIComponent(documentId)}`} className="inline-flex min-h-10 items-center rounded-full px-3 text-sm font-semibold underline underline-offset-4 focus-visible:outline-2 focus-visible:outline-accent">{t("viewExisting")}</Link>}{reason && <p className="w-full text-sm text-muted">{t("duplicate", { reason: t("reasons." + reason, { defaultValue: reason }) })}</p>}</>}
   {suspect && <Pill className="gap-2 whitespace-normal bg-bad/15"><AlertTriangle size={18} className="shrink-0" aria-hidden="true"/>{t("suspiciousBadge", { reason: reason && !duplicate ? t("reasons." + reason, { defaultValue: reason }) : t("results.quarantined") })}</Pill>}
   {read && !duplicate && typeof facts === "number" && <Pill className="gap-2 bg-ok/15"><StatusDot tone="ok"/>{t("extractedInfo", { count: facts })}</Pill>}
  </div>
  {error && <div role="alert" className="flex items-start gap-3 rounded-2xl border border-bad/40 bg-bad/10 p-4"><AlertTriangle aria-hidden="true" className="shrink-0"/><p className="[overflow-wrap:anywhere]">{error}</p></div>}
  {children}
 </div>;
}
