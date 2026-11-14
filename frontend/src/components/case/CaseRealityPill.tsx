import { useTranslation } from "react-i18next";
import type { components } from "@/api/schema";
import { Pill } from "@/components/bento/Pill";

export function CaseRealityPill({ value }: { value: components["schemas"]["RealityBadge"] }) {
 const { t } = useTranslation("caseDetail");
 const colors = { real: "bg-ok/10 text-emerald-900", reproduction: "bg-warn/15 text-amber-950", simulated: "bg-idle/15 text-ink" };
 return <Pill className={`max-w-full px-3 py-1 text-xs ${colors[value]}`}>{t("reality." + value)}</Pill>;
}
