import { useTranslation } from "react-i18next";
import { NumberTicker } from "@/components/bento/NumberTicker";
import { Pill } from "@/components/bento/Pill";
import { useOverview, useSavings } from "./data";

export function FleetSummary() {
 const { t } = useTranslation("parc"), overview = useOverview(), savings = useSavings();
 return <div className="flex flex-wrap gap-2 text-sm" aria-label={t("summary")}>
  <Pill className="gap-1">{overview.data ? <NumberTicker value={overview.data.length}/> : "—"} {t("equipmentCount")}</Pill>
  <Pill className="gap-1">{savings.data ? <NumberTicker value={savings.data.covered_equipment_eur} currency="EUR"/> : "—"} {t("coveredAmount")}</Pill>
  <Pill className="gap-1">{savings.data ? <NumberTicker value={savings.data.realized_savings_eur} currency="EUR"/> : "—"} {t("realizedAmount")}</Pill>
  {(overview.isError || savings.isError) && <span role="alert" className="w-full text-red-800">{t("summaryError")}</span>}
 </div>;
}
