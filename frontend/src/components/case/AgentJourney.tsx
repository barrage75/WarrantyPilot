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
 return <Tile className="min-w-0 hover:translate-y-0">
  <div className="mb-6 flex flex-wrap items-center justify-between gap-2"><h2 className="text-xl font-semibold tracking-tight">{t("journey.title")}</h2><p className="text-sm text-muted">{t("enums:CaseStatus." + item.status)}</p></div>
  <ol className="space-y-0" aria-label={t("journey.title")}>
   {stages.map((stage, index) => { const Icon = icons[index]; const done = index < current || item.status === "resolved"; return <li key={stage} aria-current={index === current ? "step" : undefined} className="relative flex min-w-0 items-start gap-4 pb-6 last:pb-0">
    {index < stages.length - 1 && <div aria-hidden="true" className="absolute left-[23px] top-12 h-[calc(100%-48px)] w-0.5 overflow-hidden bg-line">
     {index < current && <motion.span className="absolute inset-0 origin-top bg-accent" initial={reducedMotion ? false : { opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: reducedMotion ? 0 : 0.5 }}/>}
     {index === current - 1 && !reducedMotion && <motion.span className="absolute inset-x-0 top-0 h-1/3 bg-gradient-to-b from-transparent via-accent/25 to-transparent" animate={{ y: ["-100%", "400%"] }} transition={{ duration: 2, repeat: Infinity, ease: "linear" }}/>}
    </div>}
    <span aria-hidden="true" className={`relative grid h-12 w-12 shrink-0 place-items-center rounded-full ${index === current ? "bg-accent-soft text-accent ring-2 ring-accent" : done ? "bg-ok text-white" : "bg-canvas text-muted"}`}>{done ? <Check size={20}/> : <Icon size={20} strokeWidth={1.75}/>}</span>
    <span className={`pt-3 text-sm ${index === current ? "font-semibold text-ink" : "text-muted"}`}>{t("journey." + stage)}</span>
   </li>; })}
  </ol>
 </Tile>;
}
