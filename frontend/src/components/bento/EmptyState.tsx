import type { ReactNode } from "react";
import { PackageOpen } from "lucide-react";

export function EmptyState({ title, description, action, icon }: { title: string; description?: string; action?: ReactNode; icon?: ReactNode }) {
 return <div className="flex flex-col items-center gap-3 px-5 py-8 text-center">
  <span className="text-muted" aria-hidden="true">{icon ?? <PackageOpen size={28} strokeWidth={1.75}/>}</span>
  <p className="font-semibold text-ink">{title}</p>
  {description && <p className="max-w-xs text-sm text-muted">{description}</p>}
  {action}
 </div>;
}
