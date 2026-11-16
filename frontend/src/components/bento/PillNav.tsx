import { NavLink } from "react-router-dom";
import { motion, useReducedMotion } from "motion/react";
import type { LucideIcon } from "lucide-react";

export type PillNavItem = { to: string; label: string; end?: boolean; icon?: LucideIcon };
export function PillNav({ items, label }: { items: PillNavItem[]; label: string }) {
 const reducedMotion = useReducedMotion();
 return <nav aria-label={label} className="w-full min-w-0 max-w-full overflow-x-auto overscroll-x-contain [scrollbar-width:none] [&::-webkit-scrollbar]:hidden lg:fixed lg:bottom-36 lg:left-0 lg:top-32 lg:w-[264px] lg:overflow-x-hidden lg:overflow-y-auto lg:px-4">
  <div className="inline-flex min-w-max items-center gap-1 rounded-full bg-canvas p-1 lg:flex lg:w-full lg:min-w-0 lg:flex-col lg:items-stretch lg:gap-1 lg:rounded-none lg:bg-transparent lg:p-0">
   {items.map(item => <NavLink key={item.to} to={item.to} end={item.end} onFocus={event => event.currentTarget.scrollIntoView?.({ block: "nearest", inline: "nearest", behavior: "instant" })} className="relative flex scroll-mx-1 items-center gap-3 rounded-xl px-4 py-2.5 text-sm font-medium text-muted transition-colors hover:text-ink focus-visible:ring-2 focus-visible:ring-accent [&[aria-current=page]]:font-semibold [&[aria-current=page]]:text-white">
    {({ isActive }) => <>{isActive && <motion.span layoutId={reducedMotion ? undefined : "raffinee-active-nav"} transition={reducedMotion ? { duration: 0 } : { type: "spring", stiffness: 420, damping: 36 }} className="absolute inset-0 rounded-xl bg-accent"/>}{item.icon && <item.icon size={18} strokeWidth={1.8} className="relative z-10 shrink-0"/>}<span className="relative z-10">{item.label}</span></>}
   </NavLink>)}
  </div>
 </nav>;
}
