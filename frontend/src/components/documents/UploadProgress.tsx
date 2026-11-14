import { motion, useReducedMotion } from "motion/react";
import { Check, FileText } from "lucide-react";
import { useTranslation } from "react-i18next";

export function UploadProgress({ name, waiting, state, duplicate, facts }: { name: string; waiting: boolean; state?: string; duplicate?: boolean; facts?: number }) {
 const { t } = useTranslation("documents");
 const reduced = useReducedMotion();
 const verified = !!state && !duplicate;
 const read = state === "extracted";
 return <div className="min-w-0 space-y-4 rounded-2xl bg-canvas p-5">
  <div className="flex items-center gap-3"><FileText aria-hidden="true" className="shrink-0"/><p className="min-w-0 break-all font-semibold">{name}</p></div>
  <ol className="flex flex-wrap gap-x-5 gap-y-2 text-sm" aria-label={t("stepsTitle")}>
   {([ ["sent", !!state || !!duplicate], ["verified", verified], ["read", read] ] as const).map(([step, complete]) => <li key={step} className="flex items-center gap-2"><span className={complete ? "text-ink" : "text-muted"}>{t("steps." + step)}</span>{complete && <Check size={16} aria-label={t("completed")}/>}</li>)}
  </ol>
  {waiting && <><p role="status" aria-live="polite" aria-busy="true">{t("uploading")}</p><div role="progressbar" aria-label={t("uploading")} className="h-1.5 overflow-hidden rounded-full bg-line"><motion.div className="h-full w-1/3 rounded-full bg-accent" initial={false} animate={reduced ? { x: 0 } : { x: ["-100%", "300%"] }} transition={reduced ? { duration: 0 } : { duration: 1.4, repeat: Infinity, ease: "linear" }}/></div></>}
  {!waiting && state === "pending_extraction" && <p className="text-sm text-muted">{t("awaitingReading")}</p>}
  {read && typeof facts === "number" && <p className="text-sm font-medium">{t("extractedInfo", { count: facts })}</p>}
 </div>;
}
