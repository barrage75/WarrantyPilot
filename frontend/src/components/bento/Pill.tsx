import type { ComponentProps } from "react";
import { cn } from "@/lib/utils";

export function Pill({ className, ...props }: ComponentProps<"span">) {
 return <span className={cn("inline-flex items-center rounded-full bg-idle-soft px-3 py-1.5 text-sm font-medium text-ink", className)} {...props}/>;
}
