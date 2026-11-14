import type { ComponentProps } from "react";
import { cn } from "@/lib/utils";

export function Pill({ className, ...props }: ComponentProps<"span">) {
 return <span className={cn("inline-flex items-center rounded-full bg-surface px-4 py-2 text-sm font-medium text-ink", className)} {...props}/>;
}
