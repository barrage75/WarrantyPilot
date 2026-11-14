import { useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { usePreflight, useResetDemo } from "@/api/hooks";
import { apiErrorKey } from "@/api/errors";
import { useOperator } from "@/operator-state";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Dialog, DialogContent, DialogTitle, DialogDescription } from "@/components/ui/dialog";
export default function Demo() {
 const { t } = useTranslation("demo"), preflight = usePreflight(), reset = useResetDemo(), { save } = useOperator();
 const [confirm, setConfirm] = useState(false), [done, setDone] = useState(false);
 return <div className="space-y-5"><h1 className="text-3xl font-semibold">{t("title")}</h1><Card><h2 className="mb-4 text-xl font-semibold">{t("preflight")}</h2>
 {preflight.isPending && <p>{t("common:loading")}</p>}{preflight.isError && <p role="alert">{t(apiErrorKey(preflight.error))}</p>}
 <ul className="mb-6 space-y-4">{preflight.data?.checks.map(check => <li key={check.name}><strong className={check.ok ? "text-green-800" : "text-red-800"}>{check.ok ? "✓" : "✗"} {t("checkNames." + check.name, { defaultValue: check.name })}</strong><p>{check.ok ? t("checkDetails." + check.name, { defaultValue: check.detail }) : check.detail}</p>{check.ok && <details className="mt-1 text-sm text-slate-600"><summary>{t("serverDetails")}</summary><p className="mt-1 break-words">{check.detail}</p></details>}{check.fix_hint && <p className="text-sm text-amber-900">{check.fix_hint}</p>}</li>)}</ul>
 <div className="flex flex-wrap gap-3"><Button variant="outline" disabled={preflight.isFetching} onClick={() => void preflight.refetch()}>{t("common:refresh")}</Button><Button variant="destructive" disabled={reset.isPending} onClick={() => setConfirm(true)}>{t("reset")}</Button></div>
 {done && <p role="status" className="mt-4">{t("identityReset")}</p>}{reset.isError && <p role="alert">{t(apiErrorKey(reset.error))}</p>}
 <Dialog open={confirm} onOpenChange={setConfirm}><DialogContent><DialogTitle>{t("reset")}</DialogTitle><DialogDescription>{t("confirm")}</DialogDescription><p>{t("identityWarning")}</p>{reset.isError && <p role="alert">{t(apiErrorKey(reset.error))}</p>}<div className="flex gap-3"><Button variant="outline" disabled={reset.isPending} onClick={() => setConfirm(false)}>{t("common:cancel")}</Button><Button variant="destructive" disabled={reset.isPending} onClick={() => reset.mutate(undefined, { onSuccess: () => { save(""); setDone(true); setConfirm(false); toast.success(t("success")); }, onError: error => toast.error(t(apiErrorKey(error))) })}>{t("confirmReset")}</Button></div></DialogContent></Dialog>
 </Card></div>;
}
