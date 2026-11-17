import type { ComponentProps } from "react";
import { cn } from "@/lib/utils";

export function Tile({ highlight = false, span = 1, className, ...props }: ComponentProps<"article"> & { highlight?: boolean; span?: 1 | 2 }) {
 return <article className={cn("rounded-[20px] border border-line bg-surface p-6 shadow-[0_1px_2px_rgba(15,27,61,.04),0_6px_24px_rgba(37,99,235,.06)] transition-transform duration-200 ease-out hover:-translate-y-0.5 motion-reduce:transform-none", span === 2 && "md:col-span-2", highlight && "ring-2 ring-accent", className)} {...props}/>;
}
