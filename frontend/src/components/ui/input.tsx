import type { ComponentProps } from "react";
import { cn } from "@/lib/utils";
export function Input({ className, ...props }: ComponentProps<"input">) { return <input className={cn("min-h-10 w-full rounded-xl border border-line bg-surface px-4 py-2.5 text-sm text-ink placeholder:text-muted focus-visible:ring-2 focus-visible:ring-accent disabled:opacity-50", className)} {...props}/>; }
