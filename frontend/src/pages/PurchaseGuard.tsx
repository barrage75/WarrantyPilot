import { useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { motion, useReducedMotion } from "motion/react";
import { ArrowUpRight, ShieldCheck, ShoppingBag } from "lucide-react";
import { useEquipment, usePurchaseAction, usePurchaseRequests, type PurchaseAction, type PurchaseRecommendation } from "@/api/resources";
import { apiErrorKey } from "@/api/errors";
import { useOperator } from "@/operator-state";
import { Tile } from "@/components/bento/Tile";
import { Pill } from "@/components/bento/Pill";
import { StatusDot } from "@/components/bento/StatusDot";
import { EquipmentIcon } from "@/components/bento/EquipmentIcon";
import { EmptyState } from "@/components/bento/EmptyState";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
function Recommendation({ item, category, wide }: { item: PurchaseRecommendation; category: string; wide: boolean }) {
 const { t, i18n } = useTranslation("purchaseGuard");
 const { personId } = useOperator();
 const action = usePurchaseAction(item.id);
 const [reason, setReason] = useState("");
 const money = (amount: number) => new Intl.NumberFormat(i18n.language, { style: "currency", currency: "EUR" }).format(amount);
 const date = (at?: string | null) => at ? new Intl.DateTimeFormat(i18n.language).format(new Date(at)) : t("pending");
 const undecided = item.state === "recommendation" || item.state === "awaiting_decision";
 const realized = item.state === "saving_realized";
 const tone = item.verdict === "covered" ? "ok" : item.verdict === "not_covered" || item.verdict === "out_of_manufacturer" ? "bad" : "waiting";
 const verdictClass = tone === "ok" ? "bg-ok/15" : tone === "bad" ? "bg-bad/15" : "bg-warn/20";
 function run(value: PurchaseAction) { action.mutate(value, { onSuccess: () => { toast.success(t("caseDetail:actionSuccess")); setReason(""); }, onError: error => toast.error(t(apiErrorKey(error))) }); }
 return <Tile aria-label={item.equipment} className={`min-w-0 space-y-6 ${wide ? "lg:grid lg:grid-cols-2 lg:gap-6 lg:space-y-0" : ""}`}>
 <header className={`space-y-4 ${wide ? "lg:col-span-2" : ""}`}><div className="flex flex-wrap items-start justify-between gap-4"><EquipmentIcon category={category}/><Pill className="bg-canvas text-base">{money(item.amountEur)}</Pill></div><div><p className="text-sm text-muted">{item.company}</p><h2 className="break-words text-2xl font-bold tracking-tight">{item.equipment}</h2></div><Pill className="gap-2 bg-canvas"><StatusDot tone={realized ? "ok" : undecided ? "active" : "idle"}/>{t("enums:PurchaseGuardState." + item.state)}</Pill></header>
 <section className="space-y-3 self-start rounded-2xl bg-canvas p-4" aria-label={t("level1")}><h3 className="font-semibold">{t("level1")}</h3><Pill className={`gap-2 ${verdictClass}`}><StatusDot tone={tone}/>{t("enums:VerdictValue." + item.verdict)}</Pill><p className="font-medium">{t(tone === "ok" ? "advice.covered" : tone === "bad" ? "advice.notCovered" : "advice.verify")}</p><p className="text-sm leading-relaxed text-ink">{i18n.language.startsWith("fr") ? item.explanationFr : item.explanationEn}</p>
 {item.caseId && <Link className="inline-flex min-h-10 items-center gap-2 rounded-full text-sm font-semibold underline underline-offset-4 focus-visible:outline-2 focus-visible:outline-accent" to={"/cases/" + item.caseId}>{t("viewCase", { id: item.caseId.slice(0, 8) })}<ArrowUpRight size={16} aria-hidden="true"/></Link>}
 </section><section className="min-w-0 space-y-4" aria-label={t("level2")}><h3 className="font-semibold">{t("level2")}</h3>
 {undecided ? <div className="space-y-4"><Button className="w-full whitespace-normal" disabled={action.isPending} onClick={() => run({ kind: "decide", choice: "suspend" })}>{t("suspend")}</Button><form className="space-y-3" onSubmit={e => { e.preventDefault(); if (reason.trim()) run({ kind: "decide", choice: "keep", reason: reason.trim() }); }}><label className="block text-sm font-medium" htmlFor={"purchase-reason-" + item.id}>{t("reason")}</label><Textarea id={"purchase-reason-" + item.id} value={reason} onChange={e => setReason(e.target.value)} required/><Button className="w-full whitespace-normal" variant="outline" disabled={action.isPending || !reason.trim()}>{t("keep")}</Button></form></div> : <p className="break-words text-sm leading-relaxed">{t("decisionReason", { reason: item.reason ?? "—" })}</p>}
 {item.state !== "purchase_kept" && !realized && <p className="text-sm text-muted">{t("possible", { amount: money(item.amountEur) })}</p>}</section>
 <section className={`space-y-3 border-t border-line pt-5 ${wide ? "lg:col-span-2" : ""}`} aria-label={t("level3")}><h3 className="flex items-center gap-2 font-semibold"><ShieldCheck size={20} aria-hidden="true"/>{t("level3")}</h3><p className="text-sm leading-relaxed text-muted">{t("proofRequirement")}</p>
 {(item.state === "purchase_suspended" || item.state === "cancelled") && <div className="flex flex-wrap gap-3">{!personId && <p className="w-full text-sm text-amber-900">{t("common:identityRequired")}</p>}<Button variant="outline" disabled={action.isPending || !personId || !!item.cancelledAt} onClick={() => run({ kind: "confirm-cancellation" })}>{t("confirmCancellation")}</Button><Button variant="outline" disabled={action.isPending || !item.caseId || !!item.resolvedAt} onClick={() => run({ kind: "resolve-case" })}>{t("resolve")}</Button></div>}
 <p className="text-sm">{t("cancellation", { date: date(item.cancelledAt) })}</p><p className="text-sm">{t("resolution", { date: date(item.resolvedAt) })}</p>
 <p role="status" className={`rounded-2xl p-4 font-semibold ${realized ? "bg-ok/15" : "bg-canvas"}`}>{realized ? t("realized", { amount: money(item.amountEur), cancelled: date(item.cancelledAt), resolved: date(item.resolvedAt) }) : t("realizedZero", { amount: money(0) })}</p></section>
 {action.isPending && <p aria-live="polite" aria-busy="true" className="text-sm text-muted">{t("updating")}</p>}
 {action.isError && <p role="alert" className="text-red-800">{t(apiErrorKey(action.error))}</p>}
 </Tile>;
}
export default function PurchaseGuard() {
 const { t } = useTranslation("purchaseGuard");
 const query = usePurchaseRequests();
 const equipment = useEquipment();
 const reduced = useReducedMotion();
 return <div className="space-y-6 text-ink"><header className="space-y-3"><h1 className="text-4xl font-bold tracking-tight">{t("title")}</h1><p className="max-w-2xl text-muted">{t("neverBlock")}</p></header>{query.isError && <Tile><p role="alert">{t(apiErrorKey(query.error))}</p></Tile>}{query.isPending && <p role="status">{t("common:loading")}</p>}{query.data?.length === 0 && <Tile><EmptyState title={t("empty")} icon={<ShoppingBag size={32} strokeWidth={1.75}/>}/></Tile>}<div className="grid grid-cols-1 items-start gap-4 md:grid-cols-2 xl:grid-cols-4">{query.data?.map((item, index) => {
  const categories = new Set(equipment.data?.filter(candidate => `${candidate.brand} ${candidate.model}` === item.equipment).map(candidate => candidate.category));
  const category = categories.size === 1 ? [...categories][0] : "package";
  const wide = query.data.length === 1;
  return <motion.div key={item.id} className={`min-w-0 md:col-span-2 ${wide ? "xl:col-span-4" : ""}`} initial={reduced ? false : { opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: reduced ? 0 : 0.25, delay: reduced ? 0 : index * 0.04 }}><Recommendation item={item} category={category} wide={wide}/></motion.div>;
 })}</div></div>;
}
