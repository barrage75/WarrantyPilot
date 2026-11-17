import { useQuery } from "@tanstack/react-query";
import { client, unwrap } from "@/api/client";
import { useEquipment } from "@/api/resources";
import { EquipmentIcon } from "@/components/bento/EquipmentIcon";
import { WarrantyRing } from "@/components/bento/WarrantyRing";
import { useTranslation } from "react-i18next";

export function CaseEquipment({ equipmentId }: { equipmentId?: string | null }) {
 const { t, i18n } = useTranslation(["caseDetail", "parc"]), equipment = useEquipment();
 const overview = useQuery({ queryKey: ["case-equipment-overview"], queryFn: async () => unwrap(await client.GET("/api/equipment/overview")), staleTime: 60000 });
 const item = equipment.data?.find(item => item.id === equipmentId);
 const warranty = overview.data?.find(item => item.equipment_id === equipmentId);
 const date = warranty?.warranty_end ? new Intl.DateTimeFormat(i18n.language, { dateStyle: "long" }).format(new Date(`${warranty.warranty_end}T00:00:00`)) : t("parc:unknown");
 return <div className="space-y-5">
  <div className="flex items-center justify-between gap-4"><EquipmentIcon category={item?.category ?? warranty?.category ?? "package"} size={80}/><WarrantyRing daysLeft={warranty?.days_left ?? null} coverage={warranty?.coverage ?? "unknown"}/></div>
  <div><h3 className="font-semibold">{item ? `${item.brand} ${item.model}` : t("equipmentUnknown")}</h3><p className="mt-1 text-sm text-muted">{item?.serial ?? "—"}</p></div>
  <dl className="space-y-2 border-t border-line pt-4 text-sm"><div className="flex justify-between gap-3"><dt className="text-muted">{t("parc:warrantyEnd")}</dt><dd className="text-right font-medium">{date}</dd></div>{warranty && <div className="flex justify-between gap-3"><dt className="text-muted">{t("parc:coverageLabel")}</dt><dd className="text-right font-medium">{t("parc:coverage." + warranty.coverage)}</dd></div>}</dl>
 </div>;
}
