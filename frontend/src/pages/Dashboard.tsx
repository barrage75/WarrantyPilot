import { useState } from "react";
import { useTranslation } from "react-i18next";
import { startScan, useScan } from "@/api/resources";
import { apiErrorKey } from "@/api/errors";
import { CaseRealityPill as RealityPill } from "@/components/case/CaseRealityPill";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Table } from "@/components/ui/table";
import { Link } from "react-router-dom";
import { Download, ShieldCheck } from "lucide-react";
import { useSavings } from "@/components/parc/data";
import { Tile } from "@/components/bento/Tile";
export default function Dashboard() {
 const { t, i18n } = useTranslation("dashboard");
 const savings = useSavings();
 const [downloading, setDownloading] = useState(false), [downloadError, setDownloadError] = useState(false);
 const [scanId, setScanId] = useState<string>(), [starting, setStarting] = useState(false), [startError, setStartError] = useState<unknown>();
 const scan = useScan(scanId), summary = scan.data;
 const running = starting || (!!scanId && (!summary || summary.status === "running"));
 const done = summary?.status === "completed" ? summary : undefined;
 const money = (value: number, maximumFractionDigits = 0) => new Intl.NumberFormat(i18n.language, { style: "currency", currency: "EUR", maximumFractionDigits }).format(value);
 async function run() { setStarting(true); setStartError(undefined); try { setScanId((await startScan()).scan_id); } catch (error) { setStartError(error ?? true); } finally { setStarting(false); } }
 const error = startError ?? scan.error;
 async function download() {
  setDownloading(true); setDownloadError(false);
  try { const response = await fetch("/api/reports/savings.csv", { credentials: "same-origin" }); if (!response.ok) throw new Error(); const url = URL.createObjectURL(await response.blob()); const link = document.createElement("a"); link.href = url; link.download = "warrantypilot-savings.csv"; document.body.append(link); link.click(); link.remove(); window.setTimeout(() => URL.revokeObjectURL(url), 1000); } catch { setDownloadError(true); } finally { setDownloading(false); }
 }
 return <div className="space-y-6"><h1 className="text-4xl font-bold tracking-tight">{t("title")}</h1>{summary && <RealityPill value={summary.badge}/>}
 <Tile><div className="mb-5 flex flex-wrap items-center justify-between gap-4"><div><h2 className="text-xl font-semibold tracking-tight">{t("report")}</h2>{savings.data && <p className="mt-1 text-sm text-muted">{savings.data.company} · {t("generated", { date: new Date(savings.data.generated_at).toLocaleDateString(i18n.language) })}</p>}</div><Button variant="outline" onClick={() => void download()} disabled={downloading || !savings.data}><Download size={16}/>{t(downloading ? "downloading" : "download")}</Button></div>
 {savings.isPending && <p role="status">{t("common:loading")}</p>}{savings.isError && <p className="text-sm text-bad">{t("reportError")}</p>}{downloadError && <p role="alert" className="text-bad">{t("downloadError")}</p>}
 {savings.data && <><div className="mb-6 flex flex-wrap gap-3">{([['covered_equipment_eur','reportCovered'],['possible_savings_eur','reportPossible'],['realized_savings_eur','reportRealized']] as const).map(([key, label]) => <span key={key} className="rounded-full bg-canvas px-4 py-2 text-sm">{t(label)} <strong className="ml-1">{money(savings.data[key])}</strong></span>)}<Link to="/journal" className="inline-flex min-h-10 items-center gap-2 rounded-full bg-canvas px-4 py-2 text-sm underline underline-offset-4"><ShieldCheck size={16}/>{t(savings.data.journal_ok ? "journalOk" : "journalBroken")}</Link></div>
 <Table><thead><tr><th>{t("equipment")}</th><th>{t("manufacturer")}</th><th>{t("channel")}</th><th>{t("status")}</th><th>{t("amount")}</th><th>{t("result")}</th><th>{t("reference")}</th><th>{t("resolvedAt")}</th></tr></thead><tbody>{savings.data.lines.map(line => <tr key={line.case_id}><td><Link className="font-medium underline underline-offset-4" to={`/cases/${line.case_id}`}>{line.equipment_label}</Link></td><td>{line.manufacturer}</td><td>{t(`enums:Channel.${line.channel}`)}</td><td>{t(`enums:CaseStatus.${line.status}`)}</td><td className="whitespace-nowrap">{money(line.amount_eur, 2)}</td><td>{t(line.realized ? "realized" : "possible")}</td><td className="break-all">{line.reference ?? "—"}</td><td>{line.resolved_at ? new Date(line.resolved_at).toLocaleDateString(i18n.language) : "—"}</td></tr>)}</tbody></Table>{!savings.data.lines.length && <p className="py-5 text-sm text-muted">{t("noLines")}</p>}</>}
 </Tile><Card>
 <Button onClick={() => void run()} disabled={running}>{t("scan")}</Button><p className="my-3 text-sm">{t("fictional")}</p>
 {summary && summary.status === "running" && <label className="block">{t("progress", { done: summary.documentsDone, total: summary.documentsTotal || "…" })}<progress className="block w-full" aria-label={t("scan")} max={summary.documentsTotal || 1} value={summary.documentsDone}/></label>}
 {done && <p role="status">{t("complete", { count: done.invoices, done: done.documentsDone, total: done.documentsTotal })}</p>}
 {summary?.status === "failed" && <p role="alert" className="text-bad">{t("failed", { error: summary.error ?? "—" })}</p>}
 {error !== undefined && error !== null && <p role="alert" className="text-bad">{t(apiErrorKey(error))}</p>}
 <h2 className="my-4 text-xl font-semibold">{t("expiring")}</h2><Table><thead><tr><th>{t("equipment")}</th><th>{t("right")}</th><th>{t("end")}</th><th>{t("days")}</th></tr></thead><tbody>{done?.expiring.map(row => <tr key={row.equipment + row.right + row.endsAt}><td>{row.equipment}</td><td>{t("enums:RightType." + row.right)}</td><td>{new Intl.DateTimeFormat(i18n.language).format(new Date(row.endsAt))}</td><td>{row.daysLeft}</td></tr>)}</tbody></Table>{!done && <p className="mt-4 text-muted">{t("empty")}</p>}{done && !done.expiring.length && <p className="mt-4 text-muted">{t("noExpiring")}</p>}</Card></div>;
}
