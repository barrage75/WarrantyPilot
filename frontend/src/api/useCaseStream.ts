import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { client, unwrap } from "./client";
import type { StreamEventLocal } from "./untyped";
import eventLabels from "@/i18n/en/enums.json";
import { useSseEnabled } from "@/preferences";
export function mergeEvents(a: StreamEventLocal[], b: StreamEventLocal[]) {
 return [...new Map([...a, ...b].map(event => [event.seq, event])).values()].sort((x, y) => x.seq - y.seq);
}
export function useCaseStream(caseId: string) {
 const cache = useQueryClient();
 const sseEnabled = useSseEnabled();
 const [connection, setConnection] = useState<"connecting" | "open" | "error">("connecting");
 const query = useQuery({
  queryKey: ["events", caseId], enabled: !!caseId,
  refetchInterval: sseEnabled ? false : 2000,
  queryFn: async () => {
   const events = await unwrap(await client.GET("/api/cases/{case_id}/events", { params: { path: { case_id: caseId } } }));
   const previous = cache.getQueryData<StreamEventLocal[]>(["events", caseId]) ?? [];
   const lastSeq = previous.at(-1)?.seq ?? 0;
   if (events.some(event => event.seq > lastSeq)) {
    void cache.invalidateQueries({ queryKey: ["case", caseId] });
    void cache.invalidateQueries({ queryKey: ["cases"] });
    void cache.invalidateQueries({ queryKey: ["checklist", caseId] });
   }
   return mergeEvents(previous, events.map(event => ({
    ...event, at: event.at ?? "", payload: event.payload ?? {}, hash: event.hash ?? "",
   })));
  },
 });
 useEffect(() => {
  if (!caseId || !sseEnabled) return;
  let source: EventSource;
  let timer: ReturnType<typeof setTimeout>;
  let disposed = false;
  const key = ["events", caseId];
  function connect() {
   const current = cache.getQueryData<StreamEventLocal[]>(key) ?? [];
   const after = current.at(-1)?.seq ?? 0;
   source = new EventSource(`/api/cases/${encodeURIComponent(caseId)}/stream?after=${after}`);
   source.onopen = () => setConnection("open");
   const receive = (message: MessageEvent<string>) => {
    try {
     const value: unknown = JSON.parse(message.data);
     if (!value || typeof value !== "object" || !("seq" in value) || typeof value.seq !== "number" ||
      !("at" in value) || typeof value.at !== "string" || !("actor" in value) || typeof value.actor !== "string" ||
      !("type" in value) || typeof value.type !== "string" || !("hash" in value) || typeof value.hash !== "string" ||
      !("payload" in value) || !value.payload || typeof value.payload !== "object") throw new Error("Invalid event");
     cache.setQueryData<StreamEventLocal[]>(key, old => mergeEvents(old ?? [], [value as StreamEventLocal]));
     void cache.invalidateQueries({ queryKey: ["case", caseId] });
     void cache.invalidateQueries({ queryKey: ["cases"] });
     void cache.invalidateQueries({ queryKey: ["checklist", caseId] });
    } catch { setConnection("error"); }
   };
   Object.keys(eventLabels.EventType).forEach(type => source.addEventListener(type, receive as EventListener));
   source.onmessage = receive;
   source.onerror = () => { source.close(); setConnection("error"); if (!disposed) timer = setTimeout(connect, 1500); };
  }
  connect();
  return () => { disposed = true; source?.close(); clearTimeout(timer); };
 }, [caseId, cache, sseEnabled]);
 return { ...query, connection, mode: sseEnabled ? "sse" as const : "poll" as const };
}
