import { useTranslation } from "react-i18next";
import type { components } from "@/api/schema";
import { Badge } from "./ui/badge";
export function RealityBadge({ value, explain = false }: { value: components["schemas"]["RealityBadge"]; explain?: boolean }) {
 const { t } = useTranslation(["enums", "common"]);
 return <span className="inline-flex flex-wrap items-center gap-2"><Badge className={{ real: "bg-green-100 text-green-900", reproduction: "bg-orange-100 text-orange-900", simulated: "bg-slate-200 text-slate-800" }[value]}>{t(`RealityBadge.${value}`).toLocaleUpperCase()}</Badge>{explain && value === "simulated" && <span className="text-sm text-slate-600">{t("common:simulated")}</span>}</span>;
}
export function StatusBadge({ value }: { value: components["schemas"]["CaseStatus"] }) { const { t } = useTranslation("enums"); const color = ["failed", "cancelled"].includes(value) ? "bg-red-100 text-red-900" : ["sent", "resolved", "tracked"].includes(value) ? "bg-green-100 text-green-900" : ["awaiting_validation", "manual_takeover"].includes(value) ? "bg-amber-100 text-amber-900" : "bg-blue-100 text-blue-900"; return <Badge className={color}>{t(`CaseStatus.${value}`)}</Badge>; }
export function VerdictBadge({ value }: { value: components["schemas"]["VerdictValue"] }) { const { t } = useTranslation("enums"); return <Badge className={value === "covered" ? "bg-green-100 text-green-900" : value === "not_covered" || value === "out_of_manufacturer" ? "bg-red-100 text-red-900" : "bg-amber-100 text-amber-900"}>{t(`VerdictValue.${value}`)}</Badge>; }
