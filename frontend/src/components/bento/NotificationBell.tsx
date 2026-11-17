import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import * as Popover from "@radix-ui/react-popover";
import { Bell, ChevronRight } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { client, unwrap } from "@/api/client";
import type { components } from "@/api/schema";
import { Button } from "@/components/ui/button";
import { EmptyState } from "./EmptyState";

type Notification = components["schemas"]["Notification"];
const messageKey: Record<Notification["kind"], string> = {
 warranty_expiring: "kinds.warranty_expiring",
 case_awaiting_validation: "kinds.case_awaiting_validation",
 reminder_due: "kinds.reminder_due",
 return_deadline: "kinds.return_deadline",
 case_failed: "kinds.case_failed",
};
export function NotificationBell() {
 const { t } = useTranslation("bento");
 const navigate = useNavigate();
 const [open, setOpen] = useState(false);
 const query = useQuery({ queryKey: ["notifications"], queryFn: async () => unwrap(await client.GET("/api/notifications")), refetchInterval: 30_000 });
 const items = query.data ?? [];
 const count = items.filter(item => item.severity === "critical" || item.severity === "warning").length;
 return <Popover.Root open={open} onOpenChange={setOpen}>
  <Popover.Trigger asChild><Button variant="outline" aria-label={t("notifications.button", { count })} className="relative h-11 w-11 p-0"><Bell size={18}/>{count > 0 && <span className="absolute -right-1 -top-1 grid min-h-5 min-w-5 place-items-center rounded-full bg-bad px-1 text-[10px] font-bold text-white">{count > 99 ? "99+" : count}</span>}</Button></Popover.Trigger>
  <Popover.Portal><Popover.Content align="end" sideOffset={10} className="z-50 w-[min(22rem,calc(100vw-2rem))] rounded-[20px] border border-line bg-surface p-4 text-ink shadow-[0_1px_2px_rgba(15,27,61,.04),0_6px_24px_rgba(37,99,235,.06)] outline-none">
   <div className="mb-3 flex items-center justify-between"><h2 className="font-semibold">{t("notifications.title")}</h2><span className="text-xs text-muted">{count}</span></div>
   {query.isPending ? <p role="status" className="py-5 text-center text-sm text-muted">{t("notifications.loading")}</p>
    : query.isError ? <p role="alert" className="py-5 text-center text-sm text-bad">{t("notifications.error")}</p>
     : items.length === 0 ? <EmptyState title={t("notifications.empty")}/>
      : <ul className="max-h-[min(60vh,28rem)] space-y-1 overflow-y-auto">{items.map(item => {
       const params = Object.fromEntries(Object.entries(item.params).filter((entry): entry is [string, string | number | boolean] => entry[1] !== null));
       const content = t(messageKey[item.kind], params);
       const tone = item.severity === "critical" ? "text-bad" : item.severity === "warning" ? "text-warn" : "text-muted";
       return <li key={item.id}>{item.case_id ? <button type="button" onClick={() => { setOpen(false); navigate(`/cases/${item.case_id}`); }} className="flex w-full items-start justify-between gap-3 rounded-2xl p-3 text-left text-sm hover:bg-canvas focus-visible:ring-2 focus-visible:ring-accent"><span><span className={`mb-1 block text-xs font-semibold ${tone}`}>{t(`severity.${item.severity}`)}</span>{content}</span><ChevronRight size={16} className="mt-1 shrink-0 text-muted"/></button> : <div className="rounded-2xl p-3 text-sm"><span className={`mb-1 block text-xs font-semibold ${tone}`}>{t(`severity.${item.severity}`)}</span>{content}</div>}</li>;
      })}</ul>}
  </Popover.Content></Popover.Portal>
 </Popover.Root>;
}
