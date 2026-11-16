import { useQuery } from "@tanstack/react-query";
import { motion, useReducedMotion } from "motion/react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { client, unwrap } from "@/api/client";
import { EmptyState } from "@/components/bento/EmptyState";
import { StatusDot } from "@/components/bento/StatusDot";

export function NotificationList() {
 const { t, i18n } = useTranslation("home"), { t: tb } = useTranslation("bento"), reduced = useReducedMotion();
 const query = useQuery({ queryKey: ["notifications"], queryFn: async () => unwrap(await client.GET("/api/notifications")), refetchInterval: 30_000 });
 return <>{query.isPending && <p role="status">{t("common:loading")}</p>}{query.isError && <p role="alert" className="text-bad">{tb("notifications.error")}</p>}{query.data?.length === 0 && <EmptyState title={tb("notifications.empty")}/>}
  <ul className="max-h-[36rem] space-y-2 overflow-y-auto p-1">{query.data?.map((item, index) => {
   const message = tb(`kinds.${item.kind}`, item.params);
   return <motion.li key={item.id} initial={reduced ? false : { opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: reduced ? 0 : Math.min(index, 8) * 0.12, duration: reduced ? 0 : 0.25 }} className={`rounded-2xl p-4 ${item.severity === "critical" ? "bg-bad-soft" : item.severity === "warning" ? "bg-warn-soft" : "bg-canvas"}`}><div className="mb-2 flex items-center gap-2"><StatusDot tone={item.severity === "critical" ? "bad" : item.severity === "warning" ? "waiting" : "idle"}/><span className="text-xs font-semibold text-ink">{tb(`severity.${item.severity}`)}</span></div><Link className="block text-sm text-ink underline decoration-line underline-offset-4" to={item.case_id ? `/cases/${item.case_id}` : `/parc?coverage=expiring_soon`}>{message}</Link>{item.due_at && <p className="mt-2 text-xs text-muted">{t("due", { date: new Date(item.due_at).toLocaleDateString(i18n.language) })}</p>}</motion.li>;
  })}</ul>
 </>;
}
