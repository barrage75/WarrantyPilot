import { useTranslation } from "react-i18next";
import type { components } from "@/api/schema";
import { Pill } from "@/components/bento/Pill";

export function CaseRealityPill({ value }: { value: components["schemas"]["RealityBadge"] }) {
 const { t } = useTranslation("caseDetail");
 const colors = { real: "bg-ok-soft text-ink", reproduction: "bg-accent-soft text-accent", simulated: "bg-idle-soft text-ink" };
 return <Pill className={`max-w-full px-3 py-1 text-xs ${colors[value]}`}>{t("reality." + value)}</Pill>;
}
