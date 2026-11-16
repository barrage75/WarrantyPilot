import { useTranslation } from "react-i18next";
import type { components } from "@/api/schema";
import { Badge } from "./ui/badge";
export function RealityBadge({ value, explain = false }: { value: components["schemas"]["RealityBadge"]; explain?: boolean }) {
 const { t } = useTranslation(["enums", "common"]);
 return <span className="inline-flex flex-wrap items-center gap-2"><Badge className={{ real: "bg-ok-soft text-ink", reproduction: "bg-accent-soft text-accent", simulated: "bg-idle-soft text-ink" }[value]}>{t(`RealityBadge.${value}`)}</Badge>{explain && value === "simulated" && <span className="text-sm text-muted">{t("common:simulated")}</span>}</span>;
}
export function StatusBadge({ value }: { value: components["schemas"]["CaseStatus"] }) { const { t } = useTranslation("enums"); const color = ["failed", "cancelled"].includes(value) ? "bg-bad-soft text-ink" : ["sent", "resolved", "tracked"].includes(value) ? "bg-ok-soft text-ink" : ["awaiting_validation", "manual_takeover"].includes(value) ? "bg-warn-soft text-ink" : "bg-idle-soft text-ink"; return <Badge className={color}>{t(`CaseStatus.${value}`)}</Badge>; }
export function VerdictBadge({ value }: { value: components["schemas"]["VerdictValue"] }) { const { t } = useTranslation("enums"); const colors = { covered: "bg-ok-soft text-ink", likely_covered: "bg-probable-soft text-ink", to_verify: "bg-warn-soft text-ink", not_covered: "bg-idle-soft text-ink", out_of_manufacturer: "bg-violet-soft text-ink" }; return <Badge className={colors[value]}>{t(`VerdictValue.${value}`)}</Badge>; }
