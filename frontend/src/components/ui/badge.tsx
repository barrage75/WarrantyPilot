import type { ComponentProps } from "react";
import { cn } from "@/lib/utils";
export function Badge({ className, ...props }: ComponentProps<"span">) { return <span className={cn("inline-flex rounded-full px-3 py-1 text-xs font-semibold", className ?? "bg-idle-soft text-ink")} {...props} />; }
