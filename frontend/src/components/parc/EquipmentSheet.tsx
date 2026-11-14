import { motion, useReducedMotion } from "motion/react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { X, FileText, ArrowUpRight } from "lucide-react";
import { Dialog, DialogClose, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { EquipmentIcon } from "@/components/bento/EquipmentIcon";
import { WarrantyRing } from "@/components/bento/WarrantyRing";
import type { FleetEquipment } from "./data";

export function EquipmentSheet({ item, onClose, returnFocus }: { item: FleetEquipment | null; onClose: () => void; returnFocus: () => void }) {
 const { t, i18n } = useTranslation("parc"), reduced = useReducedMotion();
 const date = (value: string | null) => value ? new Intl.DateTimeFormat(i18n.language, { dateStyle: "long" }).format(new Date(value)) : t("unknown");
 return <Dialog open={!!item} onOpenChange={open => { if (!open) onClose(); }}>
  {item && <DialogContent onCloseAutoFocus={event => { event.preventDefault(); returnFocus(); }} className="w-[min(95vw,42rem)] p-0">
   <motion.div layoutId={reduced ? undefined : `equipment-${item.equipment_id}`} transition={{ duration: reduced ? 0 : 0.25 }} className="space-y-6 rounded-[28px] bg-surface p-6 sm:p-8">
    <div className="flex items-start justify-between gap-4"><EquipmentIcon category={item.category}/><div className="flex items-start gap-3"><WarrantyRing daysLeft={item.days_left} coverage={item.coverage}/><DialogClose asChild><Button variant="outline" className="h-10 w-10 p-0" aria-label={t("close")}><X size={18}/></Button></DialogClose></div></div>
    <div><DialogTitle>{item.label}</DialogTitle><DialogDescription>{item.assigned_to?.name ?? t("unassigned")} · {item.serial}</DialogDescription></div>
    <p className="text-sm text-muted">{t(`coverage.${item.coverage}`)}</p>
    <dl className="grid gap-5 sm:grid-cols-2"><div><dt className="text-sm text-muted">{t("purchaseDate")}</dt><dd className="mt-1 font-medium">{date(item.purchase_date)}</dd></div><div><dt className="text-sm text-muted">{t("warrantyEnd")}</dt><dd className="mt-1 font-medium">{date(item.warranty_end)}</dd></div></dl>
    <div className="flex flex-wrap gap-3">{item.invoice_document_id && <Button variant="outline" asChild><Link to={`/documents?document=${encodeURIComponent(item.invoice_document_id)}`}><FileText size={16}/>{t("invoice")}</Link></Button>}{item.open_case_id && <Button variant="outline" asChild><Link to={`/cases/${item.open_case_id}`}>{t("openCase")}<ArrowUpRight size={16}/></Link></Button>}<Button asChild><Link to={`/chat?message=${encodeURIComponent(t("faultMessage", { serial: item.serial }))}`}>{t("reportFault")}</Link></Button></div>
   </motion.div>
  </DialogContent>}
 </Dialog>;
}
