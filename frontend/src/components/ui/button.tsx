import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";
const buttonVariants = cva("inline-flex min-h-10 items-center justify-center gap-2 rounded-full px-5 py-2 text-sm font-semibold transition-colors focus-visible:ring-2 focus-visible:ring-accent disabled:cursor-not-allowed disabled:opacity-50", { variants: { variant: { default: "bg-ink text-white hover:bg-ink/85", outline: "border border-line bg-surface text-ink hover:bg-canvas", destructive: "bg-bad text-white hover:bg-bad/85" } }, defaultVariants: { variant: "default" } });
export function Button({ className, variant, asChild = false, ...props }: React.ComponentProps<"button"> & VariantProps<typeof buttonVariants> & { asChild?: boolean }) {
 const Comp = asChild ? Slot : "button";
 return <Comp className={cn(buttonVariants({ variant, className }))} {...props} />;
}
