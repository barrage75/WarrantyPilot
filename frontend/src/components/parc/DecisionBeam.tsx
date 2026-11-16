import type { ReactNode } from "react";
import { motion, useReducedMotion } from "motion/react";

export function DecisionBeam({ children, active }: { children: ReactNode; active: boolean }) {
 const reduced = useReducedMotion();
 return <section className={`relative isolate min-w-0 overflow-hidden rounded-[20px] border border-line bg-surface p-5 shadow-[0_1px_2px_rgba(15,27,61,.04),0_6px_24px_rgba(37,99,235,.06)] ${active ? "ring-2 ring-accent" : ""}`}>
  {active && !reduced && <motion.span
   aria-hidden="true"
   data-testid="decision-beam"
   className="pointer-events-none absolute inset-0 -z-10 rounded-[20px] border-2 border-transparent"
   animate={{ boxShadow: ["inset 0 2px 0 #2563eb", "inset -2px 0 0 #2563eb", "inset 0 -2px 0 #2563eb", "inset 2px 0 0 #2563eb", "inset 0 2px 0 #2563eb"] }}
   transition={{ duration: 4, repeat: Infinity, ease: "linear" }}
  />}
  <div className="space-y-4">{children}</div>
 </section>;
}
