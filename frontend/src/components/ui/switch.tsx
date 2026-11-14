import type { ComponentProps } from "react";
import { cn } from "@/lib/utils";
export function Switch({ checked, className, ...props }: Omit<ComponentProps<"input">, "type">) { return <input type="checkbox" role="switch" checked={checked} className={cn("h-5 w-9 cursor-pointer accent-teal-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-700", className)} {...props}/>; }
