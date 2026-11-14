import { useState } from "react";
import { useTranslation } from "react-i18next";
import { startScan, useScan } from "@/api/resources";
import { apiErrorKey } from "@/api/errors";
import { RealityBadge } from "@/components/Badges";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Table } from "@/components/ui/table";
const amounts = ["coveredEquipmentEur", "possibleSavingsEur", "realizedSavingsEur"] as const;
export default function Dashboard() {
 const { t, i18n } = useTranslation("dashboard");
 const [scanId, setScanId] = useState<string>(), [starting, setStarting] = useState(false), [startError, setStartError] = useState<unknown>();
 const scan = useScan(scanId), summary = scan.data;
 const running = starting || (!!scanId && (!summary || summary.status === "running"));
 const done = summary?.status === "completed" ? summary : undefined;
 const money = (value: number) => new Intl.NumberFormat(i18n.language, { style: "currency", currency: "EUR" }).format(value);
 async function run() { setStarting(true); setStartError(undefined); try { setScanId((await startScan()).scan_id); } catch (error) { setStartError(error ?? true); } finally { setStarting(false); } }
 const error = startError ?? scan.error;
 return <div className="space-y-5"><h1 className="text-3xl font-semibold">{t("title")}</h1>{summary && <RealityBadge value={summary.badge}/>}<div className="grid gap-4 md:grid-cols-3">{amounts.map(key => <Card key={key}><h2>{t(key)}</h2><p className="mt-3 text-3xl font-semibold">{done ? money(done[key]) : "—"}</p><p className="mt-2 text-xs text-slate-600">{t(key + "Help")}</p></Card>)}</div><Card>
 <Button onClick={() => void run()} disabled={running}>{t("scan")}</Button><p className="my-3 text-sm">{t("fictional")}</p>
 {summary && summary.status === "running" && <label className="block">{t("progress", { done: summary.documentsDone, total: summary.documentsTotal || "…" })}<progress className="block w-full" aria-label={t("scan")} max={summary.documentsTotal || 1} value={summary.documentsDone}/></label>}
 {done && <p role="status">{t("complete", { count: done.invoices, done: done.documentsDone, total: done.documentsTotal })}</p>}
 {summary?.status === "failed" && <p role="alert" className="text-red-800">{t("failed", { error: summary.error ?? "—" })}</p>}
 {error !== undefined && error !== null && <p role="alert" className="text-red-800">{t(apiErrorKey(error))}</p>}
 <h2 className="my-4 text-xl font-semibold">{t("expiring")}</h2><Table><thead><tr><th>{t("equipment")}</th><th>{t("right")}</th><th>{t("end")}</th><th>{t("days")}</th></tr></thead><tbody>{done?.expiring.map(row => <tr key={row.equipment + row.right + row.endsAt}><td>{row.equipment}</td><td>{t("enums:RightType." + row.right)}</td><td>{new Intl.DateTimeFormat(i18n.language).format(new Date(row.endsAt))}</td><td>{row.daysLeft}</td></tr>)}</tbody></Table>{!done && <p className="mt-4 text-slate-600">{t("empty")}</p>}{done && !done.expiring.length && <p className="mt-4 text-slate-600">{t("noExpiring")}</p>}</Card></div>;
}
