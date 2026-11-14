import { useTranslation } from "react-i18next";
import type { components } from "@/api/schema";
import { Badge } from "./ui/badge";
export function RealityBadge({ value, explain = false }: { value: components["schemas"]["RealityBadge"]; explain?: boolean }) {
 const { t } = useTranslation(["enums", "common"]);
 return <span className="inline-flex flex-wrap items-center gap-2"><Badge className={{ real: "bg-ok/10 text-ok", reproduction: "bg-warn/15 text-ink", simulated: "bg-idle/15 text-ink" }[value]}>{t(`RealityBadge.${value}`).toLocaleUpperCase()}</Badge>{explain && value === "simulated" && <span className="text-sm text-muted">{t("common:simulated")}</span>}</span>;
}
export function StatusBadge({ value }: { value: components["schemas"]["CaseStatus"] }) { const { t } = useTranslation("enums"); const color = ["failed", "cancelled"].includes(value) ? "bg-bad/10 text-bad" : ["sent", "resolved", "tracked"].includes(value) ? "bg-ok/10 text-ok" : ["awaiting_validation", "manual_takeover"].includes(value) ? "bg-warn/15 text-ink" : "bg-idle/15 text-ink"; return <Badge className={color}>{t(`CaseStatus.${value}`)}</Badge>; }
export function VerdictBadge({ value }: { value: components["schemas"]["VerdictValue"] }) { const { t } = useTranslation("enums"); return <Badge className={value === "covered" ? "bg-ok/10 text-ok" : value === "not_covered" || value === "out_of_manufacturer" ? "bg-bad/10 text-bad" : "bg-warn/15 text-ink"}>{t(`VerdictValue.${value}`)}</Badge>; }
