import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

type Coverage = "active" | "expiring_soon" | "expired" | "leased" | "unknown";
const colorClass: Record<Coverage, string> = { active: "text-ok", expiring_soon: "text-warn", expired: "text-bad", leased: "text-idle", unknown: "text-idle" };
export function WarrantyRing({ daysLeft, coverage, totalDays }: { daysLeft: number | null; coverage: Coverage; totalDays?: number }) {
 const { t, i18n } = useTranslation("bento");
 const [revealed, setRevealed] = useState(false);
 useEffect(() => { setRevealed(true); }, []);
 const safeDays = daysLeft !== null ? Math.max(daysLeft, 0) : null;
 const years = safeDays !== null ? safeDays / 365 : 0;
 const singularYear = i18n.language.startsWith("fr") ? years < 2 : Math.round(years) === 1;
 const label = coverage === "expired" ? t("ring.expiredShort")
  : coverage === "leased" ? t("ring.leasedShort")
   : safeDays === null ? t("ring.unknownShort")
    : safeDays >= 365 ? t(singularYear ? "ring.yearShort" : "ring.yearsShort", { value: new Intl.NumberFormat(i18n.language, { maximumFractionDigits: 1 }).format(years) })
     : t("ring.daysShort", { value: safeDays });
 const accessible = coverage === "leased" ? t("ring.accessible.leased")
  : coverage === "expired" ? t("ring.accessible.expired")
   : safeDays === null || coverage === "unknown" ? t("ring.accessible.unknown")
    : t("ring.accessible.remaining", { count: safeDays });
 const radius = 27, circumference = 2 * Math.PI * radius;
 const progress = coverage === "expired" || coverage === "leased" || coverage === "unknown" || safeDays === null ? 0 : Math.min(safeDays / (totalDays ?? 365), 1);
 const color = coverage === "active" ? "ok" : coverage === "expiring_soon" ? "warn" : coverage === "expired" ? "bad" : "idle";
 return <div role="img" aria-label={accessible} data-coverage={coverage} data-color={color} className={`relative grid h-16 w-16 shrink-0 place-items-center ${colorClass[coverage]}`}>
  <svg aria-hidden="true" viewBox="0 0 64 64" className="absolute inset-0 h-full w-full -rotate-90">
   <circle cx="32" cy="32" r={radius} fill="none" stroke="var(--color-line)" strokeWidth="5"/>
   <circle cx="32" cy="32" r={radius} fill="none" stroke="currentColor" strokeWidth="5" strokeLinecap="round" strokeDasharray={circumference} strokeDashoffset={circumference * (1 - (revealed ? progress : 0))} className="transition-[stroke-dashoffset] duration-[600ms] ease-out"/>
  </svg>
  <span className="relative text-xs font-semibold text-ink">{label}</span>
 </div>;
}
