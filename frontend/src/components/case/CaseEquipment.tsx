import { useQuery } from "@tanstack/react-query";
import { client, unwrap } from "@/api/client";
import { useEquipment } from "@/api/resources";
import { EquipmentIcon } from "@/components/bento/EquipmentIcon";
import { WarrantyRing } from "@/components/bento/WarrantyRing";

export function CaseEquipment({ equipmentId }: { equipmentId?: string | null }) {
 const equipment = useEquipment();
 const overview = useQuery({ queryKey: ["case-equipment-overview"], queryFn: async () => unwrap(await client.GET("/api/equipment/overview")), staleTime: 60000 });
 const item = equipment.data?.find(item => item.id === equipmentId);
 const warranty = overview.data?.find(item => item.equipment_id === equipmentId);
 return <div className="flex items-center justify-between gap-4">
  <EquipmentIcon category={item?.category ?? warranty?.category ?? "package"}/>
  <WarrantyRing daysLeft={warranty?.days_left ?? null} coverage={warranty?.coverage ?? "unknown"}/>
 </div>;
}
