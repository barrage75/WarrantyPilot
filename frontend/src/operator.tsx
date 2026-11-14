import { useId, useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { usePeople } from "@/api/resources";
import { OperatorContext, validUuid, useOperator } from "./operator-state";
function readIdentity() { try { const value = localStorage.getItem("wp-person-id") ?? ""; return validUuid(value) ? value : ""; } catch { return ""; } }
export function OperatorProvider({ children }: { children: ReactNode }) {
 const [personId, setPersonId] = useState(readIdentity);
 function save(value: string) { const id = value.trim(); if (id && !validUuid(id)) return; setPersonId(id); try { localStorage.setItem("wp-person-id", id); } catch { /* Storage may be unavailable. */ } }
 return <OperatorContext.Provider value={{ personId, save }}>{children}</OperatorContext.Provider>;
}
export function OperatorSelector() {
 const { t } = useTranslation("common");
 const { personId, save } = useOperator();
 const people = usePeople();
 const fieldId = useId();
 const active = people.data?.find(person => person.id === personId);
 const unknown = !!personId && !!people.data && !active;
 return <div className="max-w-md space-y-1 text-sm">
 <label htmlFor={fieldId} className="font-medium">{t("operator")}</label>
 <select id={fieldId} className="block w-full rounded-md border border-slate-300 bg-white p-2" aria-describedby={fieldId + "-help"} disabled={!people.data} value={active ? personId : ""} onChange={event => save(event.target.value)}>
  <option value="">{t(people.isPending ? "loading" : "choosePerson")}</option>
  {people.data?.map(person => <option key={person.id} value={person.id}>{person.name}{person.role ? " · " + person.role : ""}</option>)}
 </select>
 <p id={fieldId + "-help"} className="text-xs text-slate-600">{t("operatorHelp")}</p>
 {people.isError && <p role="alert" className="text-red-800">{t("peopleError")}</p>}
 {unknown && <p role="alert" className="text-red-800">{t("unknownPerson")}</p>}
 <p className="text-xs">{active ? t("operatorActive", { name: active.name }) : t("identityRequired")}</p></div>;
}
