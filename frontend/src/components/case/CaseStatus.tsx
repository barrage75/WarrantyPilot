import { useTranslation } from "react-i18next";
import type { components } from "@/api/schema";
import { StatusDot } from "@/components/bento/StatusDot";

type Status = components["schemas"]["CaseStatus"];
import { caseTone } from "./caseState";
export function CaseStatus({ status }: { status: Status }) {
 const { t } = useTranslation("enums");
 return <span className="inline-flex items-center gap-2 text-sm font-medium text-ink"><StatusDot tone={caseTone(status)}/>{t("CaseStatus." + status)}</span>;
}
