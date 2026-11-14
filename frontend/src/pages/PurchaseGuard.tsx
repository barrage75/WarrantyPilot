import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { MockPurchaseGuardApi, type PurchaseGuardApi, type PurchaseRecommendation } from "@/api/mocks";
import { RealityBadge } from "@/components/Badges";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
const mockApi = new MockPurchaseGuardApi();
export default function PurchaseGuard({ api = mockApi }: { api?: PurchaseGuardApi }) {
 const { t, i18n } = useTranslation("purchaseGuard");
 const [items, setItems] = useState<PurchaseRecommendation[]>(), [error, setError] = useState(false), [busy, setBusy] = useState(false), [reason, setReason] = useState("");
 useEffect(() => { let active = true; void api.recommendations().then(value => { if (active) setItems(value); }).catch(() => { if (active) setError(true); }); return () => { active = false; }; }, [api]);
 async function act(work: Promise<PurchaseRecommendation>) { setBusy(true); setError(false); try { const updated = await work; setItems(old => old?.map(item => item.id === updated.id ? updated : item)); } catch { setError(true); } finally { setBusy(false); } }
 const money = (amount: number) => new Intl.NumberFormat(i18n.language, { style: "currency", currency: "EUR" }).format(amount);
 const date = (at?: string) => at ? new Intl.DateTimeFormat(i18n.language).format(new Date(at)) : t("pending");
 return <div className="space-y-5"><h1 className="text-3xl font-semibold">{t("title")}</h1><RealityBadge value="simulated" explain/><p>{t("neverBlock")}</p>{error && <p role="alert">{t("common:error")}</p>}{!items && !error && <p>{t("common:loading")}</p>}{items?.length === 0 && <p>{t("empty")}</p>}{items?.map(item => <Card key={item.id} className="space-y-4"><h2 className="text-xl font-semibold">{item.company} · {item.equipment}</h2><p className="font-medium">{t("enums:PurchaseGuardState." + item.state)}</p>
 <h3 className="font-semibold">{t("level1")}</h3><p>{t("recommendation")}</p>
 {item.state === "recommendation" && <Button onClick={() => setItems(old => old?.map(row => row.id === item.id ? { ...row, state: "awaiting_decision" } : row))}>{t("review")}</Button>}
 <h3 className="font-semibold">{t("level2")}</h3>
 {item.state === "awaiting_decision" && <div className="space-y-3"><Button disabled={busy} onClick={() => void act(api.decide(item, "suspend"))}>{t("suspend")}</Button><form className="space-y-2" onSubmit={e => { e.preventDefault(); if (reason.trim()) void act(api.decide(item, "keep", reason)); }}><label htmlFor={"purchase-reason-" + item.id}>{t("reason")}</label><Textarea id={"purchase-reason-" + item.id} value={reason} onChange={e => setReason(e.target.value)} required/><Button variant="outline" disabled={busy || !reason.trim()}>{t("keep")}</Button></form></div>}
 {item.reason && <p>{t("reason")}: {item.reason}</p>}
 <p>{t("possible", { amount: money(item.state === "purchase_suspended" ? item.amountEur : 0) })}</p>
 <h3 className="font-semibold">{t("level3")}</h3><p>{t("proofRequirement")}</p>
 {item.state === "purchase_suspended" && <div className="flex flex-wrap gap-3"><Button variant="outline" disabled={busy || !!item.cancelledAt} onClick={() => void act(api.confirmCancellation(item))}>{t("confirmCancellation")}</Button><Button variant="outline" disabled={busy || !!item.resolvedAt} onClick={() => void act(api.resolveCase(item))}>{t("resolve")}</Button></div>}
 <p>{t("cancellation", { date: date(item.cancelledAt) })}</p><p>{t("resolution", { date: date(item.resolvedAt) })}</p>
 <p role="status" className="font-semibold">{item.state === "saving_realized" && item.cancelledAt && item.resolvedAt ? t("realized", { amount: money(item.amountEur), cancelled: date(item.cancelledAt), resolved: date(item.resolvedAt) }) : t("realizedZero", { amount: money(0) })}</p>
 </Card>)}</div>;
}
