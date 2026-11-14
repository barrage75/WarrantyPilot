import type { ReactNode } from "react";
import { motion, useReducedMotion } from "motion/react";

export function DecisionBeam({ children, active }: { children: ReactNode; active: boolean }) {
 const reduced = useReducedMotion();
 return <section className={`relative isolate min-w-0 overflow-hidden rounded-[28px] bg-surface p-6 ${active ? "ring-2 ring-accent" : ""}`}>
  {active && !reduced && <motion.span
   aria-hidden="true"
   data-testid="decision-beam"
   className="pointer-events-none absolute inset-0 -z-10 rounded-[28px] border-2 border-transparent"
   animate={{ boxShadow: ["inset 0 2px 0 #6366f1", "inset -2px 0 0 #6366f1", "inset 0 -2px 0 #6366f1", "inset 2px 0 0 #6366f1", "inset 0 2px 0 #6366f1"] }}
   transition={{ duration: 4, repeat: Infinity, ease: "linear" }}
  />}
  <div className="space-y-4">{children}</div>
 </section>;
}
