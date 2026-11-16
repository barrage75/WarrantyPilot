import { useDeferredValue, useEffect, useState } from "react";
import { Command } from "cmdk";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Search, X, ArrowUpRight, CirclePlus, Folder } from "lucide-react";
import { client, unwrap } from "@/api/client";
import { EquipmentIcon } from "@/components/bento/EquipmentIcon";
import { useOperator } from "@/operator-state";
import { Button } from "@/components/ui/button";
import "./command.css";

const pages = [["home", "/"], ["parc", "/parc"], ["cases", "/cases"], ["chat", "/chat"], ["documents", "/documents"], ["dashboard", "/dashboard"], ["purchaseGuard", "/purchase-guard"], ["journal", "/journal"], ["settings", "/settings"], ["demo", "/demo"]] as const;
export function CommandPalette() {
 const { t } = useTranslation("command"), { t: translate } = useTranslation(), navigate = useNavigate(), { isAdmin } = useOperator();
 const [open, setOpen] = useState(false), [search, setSearch] = useState("");
 const q = useDeferredValue(search.trim());
 useEffect(() => {
  function keydown(event: KeyboardEvent) { if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") { event.preventDefault(); setOpen(value => !value); } }
  document.addEventListener("keydown", keydown); return () => document.removeEventListener("keydown", keydown);
 }, []);
 const equipment = useQuery({ queryKey: ["command-equipment", q], queryFn: async ({ signal }) => unwrap(await client.GET("/api/equipment/overview", { params: { query: { q: q || undefined } }, signal })), enabled: open, staleTime: 15_000 });
 const cases = useQuery({ queryKey: ["cases"], queryFn: async () => unwrap(await client.GET("/api/cases")), enabled: open });
 const matchedEquipment = (equipment.data ?? []).slice(0, 6);
 const matchedCases = (cases.data ?? []).filter(item => `${item.id} ${equipment.data?.find(device => device.equipment_id === item.equipment_id)?.label ?? ""} ${translate(`enums:CaseStatus.${item.status}`)}`.toLocaleLowerCase().includes(q.toLocaleLowerCase())).slice(0, 5);
 const matchedPages = pages.filter(([ns, path]) => (isAdmin || !["/demo", "/settings"].includes(path)) && translate(`${ns}:title`).toLocaleLowerCase().includes(q.toLocaleLowerCase()));
 function go(path: string) { setOpen(false); setSearch(""); navigate(path); }
 return <>
  <Button variant="outline" className="h-10 min-w-0 justify-start gap-2 border-line px-3 text-muted sm:w-[min(24vw,290px)] sm:px-4 xl:w-[380px] xl:shrink-0" aria-label={t("open")} data-testid="command-trigger" onClick={() => setOpen(true)}><Search size={17} className="shrink-0"/><span className="hidden min-w-0 flex-1 truncate text-left sm:inline xl:text-xs">{t("input")}</span><kbd className="hidden shrink-0 rounded-md bg-canvas px-1.5 py-0.5 text-[11px] text-muted lg:inline">{t("shortcut")}</kbd></Button>
  <Command.Dialog open={open} onOpenChange={setOpen} label={t("title")} shouldFilter={false} overlayClassName="command-overlay" contentClassName="command-dialog">
   <div className="flex items-center gap-3 border-b border-line px-5"><Search size={20} className="shrink-0 text-muted"/><Command.Input value={search} onValueChange={setSearch} aria-label={t("input")} placeholder={t("placeholder")} className="min-w-0 flex-1 bg-transparent py-5 text-base outline-none"/><button type="button" aria-label={t("close")} className="grid h-10 w-10 shrink-0 place-items-center rounded-full hover:bg-canvas" onClick={() => setOpen(false)}><X size={18}/></button></div>
   <Command.List aria-label={t("results")} className="max-h-[min(65vh,34rem)] overflow-y-auto p-3">
    {(equipment.isPending || cases.isPending) && <Command.Loading><p role="status" className="p-3 text-sm text-muted">{t("common:loading")}</p></Command.Loading>}
    {(equipment.isError || cases.isError) && <p role="alert" className="p-3 text-sm text-bad">{t("error")}</p>}
    {matchedEquipment.length > 0 && <Command.Group heading={t("equipment")}>{matchedEquipment.map(item => <Command.Item key={item.equipment_id} value={item.equipment_id} onSelect={() => go(`/parc?q=${encodeURIComponent(item.serial)}`)}><EquipmentIcon category={item.category} size={22}/><span className="min-w-0 flex-1"><span className="block truncate font-medium">{item.label}</span><span className="block truncate text-xs text-muted">{item.serial} · {item.assigned_to?.name ?? t("unassigned")}</span></span><ArrowUpRight size={15}/></Command.Item>)}</Command.Group>}
    {matchedCases.length > 0 && <Command.Group heading={t("cases")}>{matchedCases.map(item => <Command.Item key={item.id} value={`case-${item.id}`} onSelect={() => go(`/cases/${item.id}`)}><Folder size={20}/><span className="min-w-0 flex-1 truncate">{equipment.data?.find(device => device.equipment_id === item.equipment_id)?.label ?? `#${item.id?.slice(0, 8)}`}<span className="ml-2 text-xs text-muted">{translate(`enums:CaseStatus.${item.status}`)}</span></span></Command.Item>)}</Command.Group>}
    {matchedPages.length > 0 && <Command.Group heading={t("pages")}>{matchedPages.map(([ns, path]) => <Command.Item key={path} value={path} onSelect={() => go(path)}><ArrowUpRight size={18}/>{translate(`${ns}:title`)}</Command.Item>)}</Command.Group>}
    <Command.Group heading={t("actions")}><Command.Item value="report-fault" onSelect={() => go(`/chat?message=${encodeURIComponent(t("faultMessage", { serial: matchedEquipment.length === 1 ? matchedEquipment[0].serial : q }))}`)}><CirclePlus size={20}/>{t("reportFault")}{matchedEquipment.length === 1 && <span className="truncate text-xs text-muted">{matchedEquipment[0].serial}</span>}</Command.Item></Command.Group>
   </Command.List>
  </Command.Dialog>
 </>;
}
