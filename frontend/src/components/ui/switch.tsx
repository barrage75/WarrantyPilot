import type { ComponentProps } from "react";
import { cn } from "@/lib/utils";
export function Switch({ checked, className, ...props }: Omit<ComponentProps<"input">, "type">) { return <input type="checkbox" role="switch" checked={checked} className={cn("h-5 w-9 cursor-pointer accent-accent focus-visible:ring-2 focus-visible:ring-accent", className)} {...props}/>; }
