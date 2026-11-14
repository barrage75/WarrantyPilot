import type { ComponentProps } from "react";
export function Table(props: ComponentProps<"table">) { return <div className="overflow-x-auto"><table className="w-full text-left text-sm [&_th]:p-3 [&_td]:p-3 [&_tr]:border-b [&_tr]:border-slate-200" {...props}/></div>; }
