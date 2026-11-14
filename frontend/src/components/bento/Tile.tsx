import type { ComponentProps } from "react";
import { cn } from "@/lib/utils";

export function Tile({ highlight = false, span = 1, className, ...props }: ComponentProps<"article"> & { highlight?: boolean; span?: 1 | 2 }) {
 return <article className={cn("rounded-[28px] bg-surface p-6 transition duration-200 ease-out hover:-translate-y-0.5 hover:shadow-[0_8px_30px_rgba(0,0,0,.06)] motion-reduce:transform-none", span === 2 && "md:col-span-2", highlight && "ring-2 ring-accent", className)} {...props}/>;
}
