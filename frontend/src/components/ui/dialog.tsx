import * as DialogPrimitive from "@radix-ui/react-dialog";
import type { ComponentProps } from "react";
import { cn } from "@/lib/utils";
export function Dialog(props: ComponentProps<typeof DialogPrimitive.Root>) { return <DialogPrimitive.Root {...props}/>; }
export function DialogContent({ className, children, ...props }: ComponentProps<typeof DialogPrimitive.Content>) {
 return <DialogPrimitive.Portal><DialogPrimitive.Overlay data-testid="dialog-overlay" className="fixed inset-0 z-40 bg-ink/40"/><div className="pointer-events-none fixed inset-0 z-50 flex items-center justify-center p-4"><DialogPrimitive.Content data-dialog-panel className={cn("pointer-events-auto max-h-[95vh] w-[min(95vw,32rem)] overflow-auto space-y-4 rounded-[20px] border border-line bg-surface p-6 shadow-[0_1px_2px_rgba(15,27,61,.04),0_6px_24px_rgba(37,99,235,.06)]", className)} {...props}>{children}</DialogPrimitive.Content></div></DialogPrimitive.Portal>;
}
export function DialogClose(props: ComponentProps<typeof DialogPrimitive.Close>) { return <DialogPrimitive.Close {...props}/>; }
export function DialogTitle(props: ComponentProps<typeof DialogPrimitive.Title>) { return <DialogPrimitive.Title className="text-xl font-semibold" {...props}/>; }
export function DialogDescription(props: ComponentProps<typeof DialogPrimitive.Description>) { return <DialogPrimitive.Description className="text-sm text-muted" {...props}/>; }
