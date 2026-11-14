import * as DialogPrimitive from "@radix-ui/react-dialog";
import type { ComponentProps } from "react";
export function Dialog(props: ComponentProps<typeof DialogPrimitive.Root>) { return <DialogPrimitive.Root {...props}/>; }
export function DialogContent(props: ComponentProps<typeof DialogPrimitive.Content>) { return <DialogPrimitive.Portal><DialogPrimitive.Overlay className="fixed inset-0 z-40 bg-slate-950/50"/><DialogPrimitive.Content className="fixed left-1/2 top-1/2 z-50 w-[min(95vw,32rem)] -translate-x-1/2 -translate-y-1/2 space-y-4 rounded-xl bg-white p-6 shadow-xl" {...props}/></DialogPrimitive.Portal>; }
export function DialogTitle(props: ComponentProps<typeof DialogPrimitive.Title>) { return <DialogPrimitive.Title className="text-xl font-semibold" {...props}/>; }
export function DialogDescription(props: ComponentProps<typeof DialogPrimitive.Description>) { return <DialogPrimitive.Description className="text-sm text-slate-600" {...props}/>; }
