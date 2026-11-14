import { useId, useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { OperatorContext, validUuid, useOperator } from "./operator-state";
function readIdentity() { try { const value = localStorage.getItem("wp-person-id") ?? ""; return validUuid(value) ? value : ""; } catch { return ""; } }
export function OperatorProvider({ children }: { children: ReactNode }) {
 const [personId, setPersonId] = useState(readIdentity);
 function save(value: string) { const id = value.trim(); if (id && !validUuid(id)) return; setPersonId(id); try { localStorage.setItem("wp-person-id", id); } catch { /* Storage may be unavailable. */ } }
 return <OperatorContext.Provider value={{ personId, save }}>{children}</OperatorContext.Provider>;
}
export function OperatorSelector() {
 const { personId } = useOperator();
 return <OperatorForm key={personId}/>;
}
function OperatorForm() {
 const { t } = useTranslation("common");
 const { personId, save } = useOperator();
 const [draft, setDraft] = useState(personId);
 const fieldId = useId();
 const invalid = !!draft && !validUuid(draft.trim());
 return <form className="max-w-md space-y-1 text-sm" onSubmit={e => { e.preventDefault(); save(draft); }}>
 <label htmlFor={fieldId} className="font-medium">{t("operator")}</label>
 <div className="flex gap-2"><Input id={fieldId} value={draft} aria-invalid={invalid} aria-describedby={fieldId + "-help"} onChange={e => setDraft(e.target.value)} placeholder={t("uuid")}/><Button variant="outline" disabled={invalid}>{t("save")}</Button><Button type="button" variant="outline" onClick={() => { save(""); setDraft(""); }}>{t("clear")}</Button></div>
 <p id={fieldId + "-help"} className="text-xs text-slate-600">{t("operatorHelp")}</p>
 {invalid && <p role="alert" className="text-red-800">{t("invalidUuid")}</p>}
 <p className="text-xs">{personId ? t("operatorActive", { id: personId }) : t("identityRequired")}</p></form>;
}
