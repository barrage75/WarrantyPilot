import { useSyncExternalStore } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { motion, useReducedMotion } from "motion/react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { client, unwrap } from "@/api/client";
import { apiErrorKey } from "@/api/errors";
import { cancelValidation, isValidationPending, queueValidation, subscribeValidation } from "@/lib/pendingValidation";
import { Button } from "@/components/ui/button";

export function PendingValidationButton({ caseId, disabled, onError, beam = true }: { caseId: string; disabled?: boolean; onError?: (error: unknown) => void; beam?: boolean }) {
 const { t } = useTranslation("caseDetail");
 const cache = useQueryClient();
 const reducedMotion = useReducedMotion();
 const pending = useSyncExternalStore(subscribeValidation, () => isValidationPending(caseId));
 function schedule() {
  const toastId = `validation-${caseId}`;
  const queued = queueValidation(caseId, async () => {
   toast.dismiss(toastId);
   await unwrap(await client.POST("/api/cases/{case_id}/validate", { params: { path: { case_id: caseId } }, body: {} }));
   await Promise.all([["cases"], ["case", caseId], ["checklist", caseId], ["events", caseId], ["actions", caseId], ["journal"], ["notifications"]].map(queryKey => cache.invalidateQueries({ queryKey })));
   toast.success(t("actionSuccess"));
  }, error => { toast.error(t(apiErrorKey(error))); onError?.(error); });
  if (!queued) return;
  toast(t("validationPending"), {
   id: toastId, duration: 5000,
   action: { label: t("common:cancel"), onClick: () => { if (cancelValidation(caseId)) toast.dismiss(toastId); } },
  });
 }
 return <span className={`relative inline-flex max-w-full overflow-hidden rounded-full p-[2px] ${beam ? "bg-accent" : ""}`}>
  {beam && !reducedMotion && !pending && <motion.span aria-hidden="true" className="pointer-events-none absolute -inset-full bg-[conic-gradient(from_0deg,transparent_65%,#c7d2fe_85%,#6366f1_100%)]" animate={{ rotate: 360 }} transition={{ duration: 4, repeat: Infinity, ease: "linear" }}/>}
  <Button className="relative" disabled={disabled || pending} onClick={schedule}>{t(pending ? "validationQueued" : "validate")}</Button>
 </span>;
}
