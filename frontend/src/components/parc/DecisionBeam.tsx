import type { ReactNode } from "react";

export function DecisionBeam({ children, active }: { children: ReactNode; active: boolean }) {
 return <div data-testid={active ? "decision-beam" : undefined} className={`min-w-0 border-l-2 py-2 pl-3 ${active ? "border-accent" : "border-transparent"}`}>{children}</div>;
}
