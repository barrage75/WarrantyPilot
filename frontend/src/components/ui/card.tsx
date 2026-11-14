import type { ComponentProps } from "react";
import { cn } from "@/lib/utils";
export function Card({ className, ...props }: ComponentProps<"section">) { return <section className={cn("rounded-[28px] bg-surface p-6", className)} {...props} />; }
