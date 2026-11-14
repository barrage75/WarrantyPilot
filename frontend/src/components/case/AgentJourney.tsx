import { Check, ClipboardCheck, FileText, Hand, Scale, Wrench } from "lucide-react";
import { motion, useReducedMotion } from "motion/react";
import { useTranslation } from "react-i18next";
import type { MethodResponse } from "openapi-fetch";
import type { client } from "@/api/client";
import type { StreamEventLocal } from "@/api/untyped";
import { Tile } from "@/components/bento/Tile";

type Case = MethodResponse<typeof client, "get", "/api/cases/{case_id}">;
const stages = ["invoice", "rules", "approval", "manufacturer", "tracking"] as const;
const icons = [FileText, Scale, Hand, Wrench, ClipboardCheck];
import { journeyStep } from "./caseState";
export function AgentJourney({ item, events }: { item: Case; events: StreamEventLocal[] }) {
 const { t } = useTranslation("caseDetail");
 const reducedMotion = useReducedMotion();
 const current = journeyStep(item, events);
 return <Tile className="min-w-0 hover:translate-y-0 hover:shadow-none">
  <div className="mb-6 flex flex-wrap items-center justify-between gap-2"><h2 className="text-xl font-semibold tracking-tight">{t("journey.title")}</h2><p className="text-sm text-muted">{t("enums:CaseStatus." + item.status)}</p></div>
  <ol className="grid grid-cols-1 sm:grid-cols-5" aria-label={t("journey.title")}>
   {stages.map((stage, index) => { const Icon = icons[index]; const done = index < current || item.status === "resolved"; return <li key={stage} aria-current={index === current ? "step" : undefined} className="relative flex min-w-0 items-center gap-4 pb-6 last:pb-0 sm:flex-col sm:gap-3 sm:pb-0 sm:text-center">
    {index < stages.length - 1 && <div aria-hidden="true" className="absolute left-[23px] top-12 h-[calc(100%-48px)] w-0.5 overflow-hidden bg-line sm:left-[calc(50%+24px)] sm:top-6 sm:h-0.5 sm:w-[calc(100%-48px)]">
     {index < current && <motion.span className="absolute inset-0 origin-top bg-accent sm:origin-left" initial={reducedMotion ? false : { opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: reducedMotion ? 0 : 0.5 }}/>}
     {index === current - 1 && !reducedMotion && <><motion.span className="absolute inset-x-0 top-0 h-1/3 bg-gradient-to-b from-transparent via-indigo-200 to-transparent sm:hidden" animate={{ y: ["-100%", "400%"] }} transition={{ duration: 2, repeat: Infinity, ease: "linear" }}/><motion.span className="absolute inset-y-0 left-0 hidden w-1/3 bg-gradient-to-r from-transparent via-indigo-200 to-transparent sm:block" animate={{ x: ["-100%", "400%"] }} transition={{ duration: 2, repeat: Infinity, ease: "linear" }}/></>}
    </div>}
    <span aria-hidden="true" className={`relative grid h-12 w-12 shrink-0 place-items-center rounded-full ${index === current ? "bg-accent/10 text-indigo-700 ring-2 ring-accent" : done ? "bg-ink text-white" : "bg-canvas text-muted"}`}>{done ? <Check size={20}/> : <Icon size={20} strokeWidth={1.75}/>}</span>
    <span className={`text-sm ${index === current ? "font-semibold text-ink" : "text-muted"}`}>{t("journey." + stage)}</span>
   </li>; })}
  </ol>
 </Tile>;
}
