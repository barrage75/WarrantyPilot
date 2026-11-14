import { useState } from "react";
import { useTranslation } from "react-i18next";
import { MockScanApi, type ScanApi, type ScanSummary } from "@/api/mocks";
import { RealityBadge } from "@/components/Badges";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Table } from "@/components/ui/table";
const mockApi = new MockScanApi();
export default function Dashboard({ api = mockApi }: { api?: ScanApi }) {
 const { t, i18n } = useTranslation("dashboard");
 const [summary, setSummary] = useState<ScanSummary>(), [progress, setProgress] = useState(0), [busy, setBusy] = useState(false), [error, setError] = useState(false);
 const money = (value: number) => new Intl.NumberFormat(i18n.language, { style: "currency", currency: "EUR" }).format(value);
 async function scan() { setBusy(true); setProgress(0); setError(false); try { setSummary(await api.scan(setProgress)); } catch { setError(true); } finally { setBusy(false); } }
 return <div className="space-y-5"><h1 className="text-3xl font-semibold">{t("title")}</h1><RealityBadge value="simulated" explain/><div className="grid gap-4 md:grid-cols-3">{(["coveredEquipmentEur", "possibleSavingsEur", "realizedSavingsEur"] as const).map(key => <Card key={key}><h2>{t(key)}</h2><p className="mt-3 text-3xl font-semibold">{money(summary?.[key] ?? 0)}</p></Card>)}</div><Card>
 <Button onClick={() => void scan()} disabled={busy}>{t("scan")}</Button><p className="my-3 text-sm">{t("fictional")}</p>
 {busy && <label className="block">{t("progress", { percent: progress })}<progress className="block w-full" aria-label={t("scan")} max={100} value={progress}/></label>}
 {summary && <p role="status">{t("complete", { count: summary.invoices })}</p>}{error && <p role="alert">{t("common:error")}</p>}
 <h2 className="my-4 text-xl font-semibold">{t("expiring")}</h2><Table><thead><tr><th>{t("equipment")}</th><th>{t("right")}</th><th>{t("end")}</th><th>{t("days")}</th></tr></thead><tbody>{summary?.expiring.map(row => <tr key={row.equipment}><td>{row.equipment}</td><td>{t("enums:RightType." + row.right)}</td><td>{new Intl.DateTimeFormat(i18n.language).format(new Date(row.endsAt))}</td><td>{Math.max(0, Math.ceil((Date.parse(row.endsAt) - Date.now()) / 86400000))}</td></tr>)}</tbody></Table>{!summary && <p className="mt-4 text-slate-600">{t("empty")}</p>}</Card></div>;
}
