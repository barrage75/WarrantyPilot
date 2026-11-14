import type { ComponentProps } from "react";
import { cn } from "@/lib/utils";
export function Textarea({ className, ...props }: ComponentProps<"textarea">) { return <textarea className={cn("min-h-24 w-full rounded-md border border-slate-300 p-3 text-sm focus-visible:outline-teal-700", className)} {...props}/>; }
