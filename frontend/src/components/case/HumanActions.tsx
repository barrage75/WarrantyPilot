import { useState, useSyncExternalStore } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import type { components } from "@/api/schema";
import { apiErrorKey } from "@/api/errors";
import { useHumanAction, type HumanAction, type ManualProof } from "@/api/human";
import { useOperator } from "@/operator-state";
import { isValidationPending, subscribeValidation } from "@/lib/pendingValidation";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Dialog, DialogContent, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { PendingValidationButton } from "./PendingValidationButton";
type Case = Pick<components["schemas"]["Case"], "id" | "status">;
function ErrorMessage({ error }: { error: unknown }) { const { t } = useTranslation(); return <p role="alert" className="py-3 text-red-800">{t(apiErrorKey(error))}</p>; }
export function HumanActions({ item, beam = true, section = "all" }: { item: Case; beam?: boolean; section?: "all" | "decision" | "resolution" }) {
 const { t } = useTranslation(["caseDetail", "common"]);
 const { personId } = useOperator();
 const action = useHumanAction(item.id ?? "");
 const [reject, setReject] = useState(false), [reason, setReason] = useState(""), [proof, setProof] = useState(""), [proofType, setProofType] = useState<ManualProof["proof_type"]>("case_number"), [proofDate, setProofDate] = useState(new Date().toISOString().slice(0, 10)), [note, setNote] = useState(""), [resolutionNote, setResolutionNote] = useState("");
 const pending = useSyncExternalStore(subscribeValidation, () => isValidationPending(item.id ?? ""));
 const [validationError, setValidationError] = useState<unknown>();
 const disabled = !personId || action.isPending || !item.id || pending;
 function submit(value: HumanAction) {
  if (disabled) return;
  action.mutate(value, { onSuccess: () => { toast.success(t("actionSuccess")); setReject(false); setReason(""); setProof(""); setNote(""); setResolutionNote(""); }, onError: error => toast.error(t(apiErrorKey(error))) });
 }
 return <div className="space-y-3">
 {!personId && <p className="text-sm text-amber-900">{t("common:identityRequired")}</p>}
 <div className="flex flex-wrap gap-2">
 {section !== "resolution" && item.status === "awaiting_validation" && <><PendingValidationButton caseId={item.id ?? ""} disabled={disabled} onError={setValidationError} beam={beam}/><Button variant="outline" disabled={disabled} onClick={() => setReject(true)}>{t("reject")}</Button></>}
 {section !== "resolution" && item.status === "failed" && <Button disabled={disabled} onClick={() => submit({ kind: "manual-takeover" })}>{t("takeover")}</Button>}
 </div>
 {section !== "resolution" && item.status === "manual_takeover" && <form className="space-y-2" onSubmit={e => { e.preventDefault(); if (proof.trim()) submit({ kind: "manual-proof", proof_type: proofType, reference: proof.trim(), proof_date: proofDate, note: note.trim() }); }}><p className="font-medium">{t("manualProof")}</p><label className="block text-sm" htmlFor={"proof-type-" + item.id}>{t("proofType")}</label><select id={"proof-type-" + item.id} className="block min-h-10 max-w-full rounded-2xl border border-line p-2" value={proofType} onChange={e => setProofType(e.target.value as ManualProof["proof_type"])}>{(["case_number", "email_message_id", "portal_screenshot", "carrier_tracking"] as const).map(value => <option key={value} value={value}>{t("proofTypes." + value)}</option>)}</select><label className="block text-sm" htmlFor={"proof-" + item.id}>{t("proofReference")}</label><input id={"proof-" + item.id} className="block w-full min-h-10 max-w-full rounded-2xl border border-line p-2" value={proof} maxLength={200} onChange={e => setProof(e.target.value)} required/><label className="block text-sm" htmlFor={"proof-date-" + item.id}>{t("proofDate")}</label><input id={"proof-date-" + item.id} type="date" className="block min-h-10 max-w-full rounded-2xl border border-line p-2" value={proofDate} onChange={e => setProofDate(e.target.value)} required/><label className="block text-sm" htmlFor={"proof-note-" + item.id}>{t("proofNote")}</label><Textarea id={"proof-note-" + item.id} value={note} maxLength={500} onChange={e => setNote(e.target.value)}/><Button disabled={disabled || !proof.trim()}>{t("submitProof")}</Button></form>}
 {section !== "decision" && ["sent", "tracked"].includes(item.status) && <form className="space-y-2" onSubmit={e => { e.preventDefault(); if (resolutionNote.trim()) submit({ kind: "resolve", note: resolutionNote.trim() }); }}><label htmlFor={"resolution-note-" + item.id}>{t("resolutionNote")}</label><Textarea id={"resolution-note-" + item.id} value={resolutionNote} onChange={e => setResolutionNote(e.target.value)} required/><Button disabled={disabled || !resolutionNote.trim()}>{t("resolveCase")}</Button></form>}
 {action.isError && <ErrorMessage error={action.error}/>}{validationError !== undefined && <ErrorMessage error={validationError}/>}
 <Dialog open={reject} onOpenChange={setReject}><DialogContent><DialogTitle>{t("reject")}</DialogTitle><DialogDescription>{t("reasonRequired")}</DialogDescription><form className="space-y-4" onSubmit={e => { e.preventDefault(); if (reason.trim()) submit({ kind: "reject", reason: reason.trim() }); }}><label htmlFor={"reason-" + item.id}>{t("reason")}</label><Textarea id={"reason-" + item.id} value={reason} onChange={e => setReason(e.target.value)} required/><div className="flex gap-3"><Button disabled={disabled || !reason.trim()}>{t("confirmReject")}</Button><Button type="button" variant="outline" onClick={() => setReject(false)}>{t("common:cancel")}</Button></div></form></DialogContent></Dialog>
 </div>;
}
