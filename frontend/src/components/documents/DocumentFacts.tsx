import { useTranslation } from "react-i18next";
import { isTechnicalValue } from "@/i18n/technical";
import { groupDocumentFacts, type DocumentFact } from "./facts";

export function DocumentFacts({ facts }: { facts: readonly DocumentFact[] }) {
 const { t, i18n } = useTranslation("documents");
 return <div className="space-y-4">{groupDocumentFacts(facts, i18n.language).map(group => <div key={group.key} className="space-y-2">
  {group.label && <h4 className="font-semibold">{group.label}</h4>}
  <dl className="space-y-2">{group.facts.map(fact => <div key={fact.field + JSON.stringify(fact.value)} className="rounded bg-slate-50 p-3 [overflow-wrap:anywhere]">
   <dt className="font-medium">{fact.label}</dt>
   {(typeof fact.value === "object" && fact.value !== null) || (typeof fact.value === "string" && isTechnicalValue(fact.value)) ? <dd><details><summary className="cursor-pointer text-sm text-slate-600">{t("technicalDetails")}</summary><pre className="mt-2 max-w-full overflow-x-auto whitespace-pre-wrap text-xs">{fact.formatted}</pre></details></dd> : <dd>{fact.formatted}</dd>}
   <dd className="text-sm text-slate-600">{t("confidence", { value: new Intl.NumberFormat(i18n.language, { style: "percent" }).format(fact.confidence) })}</dd>
  </div>)}</dl>
 </div>)}</div>;
}
