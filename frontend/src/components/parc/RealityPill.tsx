import { useTranslation } from "react-i18next";
import type { components } from "@/api/schema";
import { Pill } from "@/components/bento/Pill";

export function RealityPill({ value }: { value: components["schemas"]["RealityBadge"] }) {
 const { t } = useTranslation("enums");
 const color = { real: "bg-ok/10 text-ink", reproduction: "bg-warn/15 text-ink", simulated: "bg-idle/15 text-ink" }[value];
 return <Pill className={`px-3 py-1 text-xs ${color}`}>{t(`RealityBadge.${value}`)}</Pill>;
}
