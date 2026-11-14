import { useReducedMotion } from "motion/react";

const tones = { active: "bg-accent", waiting: "bg-warn", ok: "bg-ok", bad: "bg-bad", idle: "bg-idle" } as const;
export function StatusDot({ tone, label }: { tone: keyof typeof tones; label?: string }) {
 const reducedMotion = useReducedMotion();
 return <span className="relative inline-flex h-3 w-3 shrink-0" role={label ? "img" : undefined} aria-label={label}>
  {tone === "active" && !reducedMotion && <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-accent/60"/>}
  <span data-tone={tone} className={`relative inline-flex h-3 w-3 rounded-full ${tones[tone]}`}/>
 </span>;
}
