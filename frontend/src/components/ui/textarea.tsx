import type { ComponentProps } from "react";
import { cn } from "@/lib/utils";
export function Textarea({ className, ...props }: ComponentProps<"textarea">) { return <textarea className={cn("min-h-24 w-full rounded-2xl border border-line bg-surface p-4 text-sm text-ink placeholder:text-muted focus-visible:ring-2 focus-visible:ring-accent", className)} {...props}/>; }
