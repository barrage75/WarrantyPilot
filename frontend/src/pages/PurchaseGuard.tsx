import { useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { usePurchaseAction, usePurchaseRequests, type PurchaseAction, type PurchaseRecommendation } from "@/api/resources";
import { apiErrorKey } from "@/api/errors";
import { useOperator } from "@/operator-state";
import { VerdictBadge } from "@/components/Badges";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
function Recommendation({ item }: { item: PurchaseRecommendation }) {
 const { t, i18n } = useTranslation("purchaseGuard");
 const { personId } = useOperator();
 const action = usePurchaseAction(item.id);
 const [reason, setReason] = useState("");
 const money = (amount: number) => new Intl.NumberFormat(i18n.language, { style: "currency", currency: "EUR" }).format(amount);
 const date = (at?: string | null) => at ? new Intl.DateTimeFormat(i18n.language).format(new Date(at)) : t("pending");
 const undecided = item.state === "recommendation" || item.state === "awaiting_decision";
 const realized = item.state === "saving_realized";
 function run(value: PurchaseAction) { action.mutate(value, { onSuccess: () => { toast.success(t("caseDetail:actionSuccess")); setReason(""); }, onError: error => toast.error(t(apiErrorKey(error))) }); }
 return <Card className="space-y-4"><div className="flex flex-wrap items-center justify-between gap-3"><h2 className="text-xl font-semibold">{item.company} · {item.equipment} · {money(item.amountEur)}</h2><p className="font-medium">{t("enums:PurchaseGuardState." + item.state)}</p></div>
 <h3 className="font-semibold">{t("level1")}</h3><div className="flex flex-wrap items-center gap-3"><VerdictBadge value={item.verdict}/><p>{i18n.language.startsWith("fr") ? item.explanationFr : item.explanationEn}</p></div>
 {item.caseId && <Link className="inline-block text-sm font-semibold text-teal-800 underline" to={"/cases/" + item.caseId}>{t("viewCase", { id: item.caseId.slice(0, 8) })}</Link>}
 <h3 className="font-semibold">{t("level2")}</h3>
 {undecided ? <div className="space-y-3"><Button disabled={action.isPending} onClick={() => run({ kind: "decide", choice: "suspend" })}>{t("suspend")}</Button><form className="space-y-2" onSubmit={e => { e.preventDefault(); if (reason.trim()) run({ kind: "decide", choice: "keep", reason: reason.trim() }); }}><label htmlFor={"purchase-reason-" + item.id}>{t("reason")}</label><Textarea id={"purchase-reason-" + item.id} value={reason} onChange={e => setReason(e.target.value)} required/><Button variant="outline" disabled={action.isPending || !reason.trim()}>{t("keep")}</Button></form></div> : <p>{t("decisionReason", { reason: item.reason ?? "—" })}</p>}
 {item.state !== "purchase_kept" && !realized && <p>{t("possible", { amount: money(item.amountEur) })}</p>}
 <h3 className="font-semibold">{t("level3")}</h3><p>{t("proofRequirement")}</p>
 {(item.state === "purchase_suspended" || item.state === "cancelled") && <div className="flex flex-wrap gap-3">{!personId && <p className="w-full text-sm text-amber-900">{t("common:identityRequired")}</p>}<Button variant="outline" disabled={action.isPending || !personId || !!item.cancelledAt} onClick={() => run({ kind: "confirm-cancellation", person_id: personId })}>{t("confirmCancellation")}</Button><Button variant="outline" disabled={action.isPending || !item.caseId || !!item.resolvedAt} onClick={() => run({ kind: "resolve-case" })}>{t("resolve")}</Button></div>}
 <p>{t("cancellation", { date: date(item.cancelledAt) })}</p><p>{t("resolution", { date: date(item.resolvedAt) })}</p>
 <p role="status" className="font-semibold">{realized ? t("realized", { amount: money(item.amountEur), cancelled: date(item.cancelledAt), resolved: date(item.resolvedAt) }) : t("realizedZero", { amount: money(0) })}</p>
 {action.isError && <p role="alert" className="text-red-800">{t(apiErrorKey(action.error))}</p>}
 </Card>;
}
export default function PurchaseGuard() {
 const { t } = useTranslation("purchaseGuard");
 const query = usePurchaseRequests();
 return <div className="space-y-5"><h1 className="text-3xl font-semibold">{t("title")}</h1><p>{t("neverBlock")}</p>{query.isError && <p role="alert">{t(apiErrorKey(query.error))}</p>}{query.isPending && <p>{t("common:loading")}</p>}{query.data?.length === 0 && <p>{t("empty")}</p>}{query.data?.map(item => <Recommendation key={item.id} item={item}/>)}</div>;
}
