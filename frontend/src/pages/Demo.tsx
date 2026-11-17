import { useState } from "react";
import { motion, useReducedMotion } from "motion/react";
import { Check, CircleAlert, ClipboardCheck, RotateCcw, X } from "lucide-react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { usePreflight, useResetDemo } from "@/api/hooks";
import { apiErrorKey } from "@/api/errors";
import { Button } from "@/components/ui/button";
import { Tile } from "@/components/bento/Tile";
import { Pill } from "@/components/bento/Pill";
import { StatusDot } from "@/components/bento/StatusDot";
import { Dialog, DialogContent, DialogTitle, DialogDescription } from "@/components/ui/dialog";
const dangerButton = "bg-[color-mix(in_srgb,var(--color-bad)_75%,black)] text-white hover:bg-[color-mix(in_srgb,var(--color-bad)_65%,black)]";
export default function Demo() {
 const { t } = useTranslation("demo"), preflight = usePreflight(), reset = useResetDemo();
 const [confirm, setConfirm] = useState(false), [done, setDone] = useState(false);
 const reduced = useReducedMotion();
 return <div className="space-y-6 text-ink"><header className="space-y-3"><h1 className="text-4xl font-bold tracking-tight">{t("title")}</h1><p>{t("intro")}</p></header><div className="grid grid-cols-1 items-start gap-4 xl:grid-cols-3"><motion.div className="min-w-0 xl:col-span-2" initial={reduced ? false : { opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: reduced ? 0 : 0.25 }}><Tile className="min-w-0 space-y-5" aria-label={t("preflight")}><header className="space-y-3"><span className="inline-flex rounded-2xl bg-canvas p-3"><ClipboardCheck size={28} strokeWidth={1.75} aria-hidden="true"/></span><h2 className="text-xl font-bold tracking-tight">{t("preflight")}</h2><p className="text-sm leading-relaxed">{t("preflightHint")}</p></header>
 {preflight.data && <Pill className={`gap-2 ${preflight.data.ok ? "bg-ok/15" : "bg-bad/15"}`}><StatusDot tone={preflight.data.ok ? "ok" : "bad"}/>{t(preflight.data.ok ? "ready" : "notReady")}</Pill>}
 {preflight.isPending && <p>{t("common:loading")}</p>}{preflight.isError && <p role="alert">{t(apiErrorKey(preflight.error))}</p>}
 <ul className="divide-y divide-line">{preflight.data?.checks.map(check => <li key={check.name} className="space-y-2 py-4 first:pt-0 [overflow-wrap:anywhere]"><strong className="flex items-center gap-2">{check.ok ? <Check size={20} className="shrink-0 text-ink" aria-hidden="true"/> : <X size={20} className="shrink-0 text-bad" aria-hidden="true"/>}{t("checkNames." + check.name, { defaultValue: check.name })}<span className="sr-only">{t(check.ok ? "checkPassed" : "checkFailed")}</span></strong><p className="text-sm leading-relaxed">{check.ok ? t("checkDetails." + check.name, { defaultValue: check.detail }) : check.detail}</p>{check.ok && <details className="text-sm"><summary className="min-h-10 cursor-pointer content-center rounded-xl focus-visible:outline-2 focus-visible:outline-accent">{t("serverDetails")}</summary><p className="mt-1">{check.detail}</p></details>}{check.fix_hint && <p className="rounded-xl bg-warn/15 p-3 text-sm">{check.fix_hint}</p>}</li>)}</ul>
 <Button variant="outline" disabled={preflight.isFetching} onClick={() => void preflight.refetch()}>{t("common:refresh")}</Button>
 </Tile></motion.div><motion.div className="min-w-0" initial={reduced ? false : { opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: reduced ? 0 : 0.25, delay: reduced ? 0 : 0.04 }}><Tile className="min-w-0 space-y-5 ring-1 ring-bad/50" aria-label={t("reset")}><header className="space-y-3"><span className="inline-flex rounded-2xl bg-bad/15 p-3"><CircleAlert size={28} strokeWidth={1.75} aria-hidden="true"/></span><h2 className="text-xl font-bold tracking-tight">{t("reset")}</h2><p className="text-sm leading-relaxed">{t("resetHint")}</p></header><p className="rounded-2xl bg-bad/10 p-4 text-sm leading-relaxed [overflow-wrap:anywhere]">{t("identityWarning")}</p>
 <Button variant="destructive" className={`max-w-full whitespace-normal ${dangerButton}`} disabled={reset.isPending} onClick={() => setConfirm(true)}><RotateCcw size={16} className="shrink-0" aria-hidden="true"/>{t("reset")}</Button>
 {done && !reset.isPending && <p role="status" className="rounded-2xl bg-ok/15 p-4 text-sm">{t("identityReset")}</p>}{reset.isPending && <p role="status" aria-busy="true">{t("resetting")}</p>}{reset.isError && !confirm && <p role="alert">{t(apiErrorKey(reset.error))}</p>}
 <Dialog open={confirm} onOpenChange={setConfirm}><DialogContent className="ring-1 ring-bad/50"><DialogTitle>{t("reset")}</DialogTitle><DialogDescription>{t("confirm")}</DialogDescription><p className="rounded-2xl bg-bad/10 p-4 text-sm [overflow-wrap:anywhere]">{t("identityWarning")}</p>{reset.isError && <p role="alert">{t(apiErrorKey(reset.error))}</p>}{reset.isPending && <p aria-live="polite">{t("resetting")}</p>}<div className="flex flex-wrap gap-3"><Button variant="outline" disabled={reset.isPending} onClick={() => setConfirm(false)}>{t("common:cancel")}</Button><Button variant="destructive" className={`whitespace-normal ${dangerButton}`} disabled={reset.isPending} onClick={() => reset.mutate(undefined, { onSuccess: () => { setDone(true); setConfirm(false); toast.success(t("success")); }, onError: error => toast.error(t(apiErrorKey(error))) })}>{t("confirmReset")}</Button></div></DialogContent></Dialog>
 </Tile></motion.div></div></div>;
}
