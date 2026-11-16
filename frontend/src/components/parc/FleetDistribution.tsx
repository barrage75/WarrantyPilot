import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Tile } from "@/components/bento/Tile";
import { useOverview } from "./data";

const verdicts = [
 ["covered", "bg-accent"],
 ["likely_covered", "bg-probable"],
 ["to_verify", "bg-warn"],
 ["not_covered", "bg-idle"],
 ["out_of_manufacturer", "bg-violet"],
] as const;

export function FleetDistribution({ vertical = false }: { vertical?: boolean }) {
 const { t } = useTranslation(["parc", "enums"]);
 const query = useOverview(), items = query.data ?? [], total = items.length;
 const groups = verdicts.map(([value, color]) => ({ value, color, count: items.filter(item => item.verdict === value).length }));
 return <Tile className="min-w-0 space-y-5">
  <header className="flex flex-wrap items-baseline justify-between gap-3">
   <h2 className="text-lg font-semibold">{t("distribution.title")}</h2>
   <span className="text-sm text-muted">{t("distribution.total", { count: total })}</span>
  </header>
  {query.isPending ? <p role="status">{t("common:loading")}</p> : query.isError ? <p role="alert">{t("distribution.error")}</p> : <>
   <div aria-hidden="true" className="flex h-3 w-full overflow-hidden rounded-full bg-idle-soft">
    {groups.map(group => <span key={group.value} className={`${group.color} h-full`} style={{ width: total ? `${group.count / total * 100}%` : "0%" }}/>)}
   </div>
   <ul className={`grid gap-2 ${vertical ? "grid-cols-1" : "sm:grid-cols-2 lg:grid-cols-5"}`}>
    {groups.map(group => <li key={group.value}>
     <Link to={`/parc?verdict=${group.value}`} className="flex min-h-10 items-center gap-2 rounded-xl px-2 py-1.5 text-sm hover:bg-canvas focus-visible:ring-2 focus-visible:ring-accent">
      <span aria-hidden="true" className={`h-2.5 w-2.5 shrink-0 rounded-full ${group.color}`}/>
      <span className="min-w-0 flex-1">{t(`enums:VerdictValue.${group.value}`)}</span>
      <strong className="font-semibold tabular-nums">{group.count}</strong>
     </Link>
    </li>)}
   </ul>
  </>}
 </Tile>;
}
