import { resources } from "@/i18n";

export type DocumentFact = { field: string; value: unknown; confidence: number };
export type FactGroup = { key: string; label?: string; facts: (DocumentFact & { label: string; formatted: string })[] };

function stableValue(value: unknown): string {
 if (Array.isArray(value)) return `[${value.map(stableValue).join(",")}]`;
 if (value && typeof value === "object") return JSON.stringify(Object.entries(value).sort(([a], [b]) => a.localeCompare(b)).map(([key, child]) => [key, stableValue(child)]));
 return JSON.stringify(value) ?? "";
}

export function formatDocumentFact(fact: Pick<DocumentFact, "field" | "value">, language: string) {
 const translations = resources[language.startsWith("fr") ? "fr" : "en"].documents as { factLabels: Record<string, string>; factLine: string; yes: string; no: string };
 const labels = translations.factLabels;
 const field = /^lines\[\d+\]\.(.+)$/i.exec(fact.field)?.[1] ?? fact.field;
 const known = Object.hasOwn(labels, field);
 const label = known ? labels[field] : field.replace(/([a-z])([A-Z])/g, "$1 $2").replace(/[_.[\]]+/g, " ").trim().replace(/^./, first => first.toLocaleUpperCase(language));
 let formatted = fact.value == null ? "—" : typeof fact.value === "object" ? JSON.stringify(fact.value) : String(fact.value);
 if (typeof fact.value === "boolean") formatted = translations[fact.value ? "yes" : "no"];
 if (/(?:^|_)date$/.test(field) && typeof fact.value === "string" && /^\d{4}-\d{2}-\d{2}$/.test(fact.value)) {
  const date = new Date(fact.value + "T00:00:00Z");
  if (Number.isFinite(date.getTime()) && date.toISOString().slice(0, 10) === fact.value) formatted = new Intl.DateTimeFormat(language, { timeZone: "UTC" }).format(date);
 }
 if (["total_ttc", "unit_price_ht", "amount_eur"].includes(field) && (typeof fact.value === "number" || typeof fact.value === "string" && fact.value.trim() !== "")) {
  const amount = Number(fact.value);
  if (Number.isFinite(amount)) formatted = new Intl.NumberFormat(language, { style: "currency", currency: "EUR" }).format(amount);
 }
 return { label, formatted, known };
}

export function groupDocumentFacts(facts: readonly DocumentFact[], language: string): FactGroup[] {
 const translations = resources[language.startsWith("fr") ? "fr" : "en"].documents as { factLine: string };
 const groups = new Map<string, FactGroup>();
 const seen = new Set<string>();
 for (const fact of facts) {
  const identity = JSON.stringify([fact.field, stableValue(fact.value)]);
  if (seen.has(identity)) continue;
  seen.add(identity);
  const line = /^lines\[(\d+)\]\.(.+)$/i.exec(fact.field);
  const key = line ? String(Number(line[1])) : "header";
  if (!groups.has(key)) groups.set(key, { key, label: line ? translations.factLine.replace("{{number}}", String(Number(key) + 1)) : undefined, facts: [] });
  const { label, formatted } = formatDocumentFact(fact, language);
  groups.get(key)!.facts.push({ ...fact, label, formatted });
 }
 return [...groups.values()].sort((a, b) => a.key === "header" ? -1 : b.key === "header" ? 1 : Number(a.key) - Number(b.key));
}
