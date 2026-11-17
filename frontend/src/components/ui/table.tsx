import type { ComponentProps } from "react";
export function Table(props: ComponentProps<"table">) { return <div className="max-w-full overflow-x-auto rounded-[20px] border border-line bg-surface"><table className="w-full text-left text-sm text-ink [&_th]:p-3 [&_td]:p-3 [&_tr]:border-b [&_tr]:border-line [&_th]:text-muted" {...props}/></div>; }
