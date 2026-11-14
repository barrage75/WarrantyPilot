import { NavLink } from "react-router-dom";
import { motion, useReducedMotion } from "motion/react";

export type PillNavItem = { to: string; label: string; end?: boolean };
export function PillNav({ items, label }: { items: PillNavItem[]; label: string }) {
 const reducedMotion = useReducedMotion();
 return <nav aria-label={label} className="flex w-full min-w-0 max-w-full justify-start overflow-x-auto overscroll-x-contain [scrollbar-width:none] [&::-webkit-scrollbar]:hidden xl:justify-center">
  <div className="inline-flex min-w-max items-center gap-1 rounded-full bg-surface p-1">
   {items.map(item => <NavLink key={item.to} to={item.to} end={item.end} onFocus={event => event.currentTarget.scrollIntoView?.({ block: "nearest", inline: "nearest", behavior: "instant" })} className="relative scroll-mx-1 rounded-full px-4 py-2 text-sm font-medium text-muted transition-colors hover:text-ink focus-visible:ring-2 focus-visible:ring-accent [&[aria-current=page]]:text-white">
    {({ isActive }) => <>{isActive && <motion.span layoutId={reducedMotion ? undefined : "bento-active-nav"} transition={reducedMotion ? { duration: 0 } : { type: "spring", stiffness: 420, damping: 36 }} className="absolute inset-0 rounded-full bg-ink"/>}<span className="relative z-10">{item.label}</span></>}
   </NavLink>)}
  </div>
 </nav>;
}
