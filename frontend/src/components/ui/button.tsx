import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";
const buttonVariants = cva("inline-flex min-h-10 items-center justify-center gap-2 rounded-xl px-5 py-2 text-sm font-semibold transition-colors focus-visible:ring-2 focus-visible:ring-accent disabled:cursor-not-allowed disabled:opacity-50", { variants: { variant: { default: "bg-accent text-white hover:bg-accent-strong", outline: "border border-accent/30 bg-surface text-accent hover:bg-accent-soft", destructive: "bg-bad text-white hover:bg-bad/90" } }, defaultVariants: { variant: "default" } });
export function Button({ className, variant, asChild = false, ...props }: React.ComponentProps<"button"> & VariantProps<typeof buttonVariants> & { asChild?: boolean }) {
 const Comp = asChild ? Slot : "button";
 return <Comp className={cn(buttonVariants({ variant, className }))} {...props} />;
}
