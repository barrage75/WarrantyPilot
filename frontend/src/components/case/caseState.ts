import type { MethodResponse } from "openapi-fetch";
import type { client } from "@/api/client";
import type { components } from "@/api/schema";
import type { StreamEventLocal } from "@/api/untyped";
type Case = MethodResponse<typeof client, "get", "/api/cases/{case_id}">;
type Status = components["schemas"]["CaseStatus"];
export const caseChannel = (item: Case) => item.verdict?.channel ?? item.channel;
export function journeyStep(item: Case, events: StreamEventLocal[]) {
 const has = (...types: string[]) => events.some(event => types.includes(event.type));
 if (["sent", "tracked", "resolved"].includes(item.status) || has("action_succeeded", "followup_received")) return 4;
 if (["sending", "failed", "manual_takeover"].includes(item.status) || has("validated", "action_started")) return 3;
 if (item.status === "awaiting_validation" || has("validation_requested", "policy_decided")) return 2;
 if (item.verdict || has("verdict_computed", "fact_extracted")) return 1;
 return 0;
}
export function caseTone(status: Status) {
 if (status === "prepared" || status === "sending") return "active";
 if (status === "awaiting_validation" || status === "sent" || status === "tracked") return "waiting";
 if (status === "resolved") return "ok";
 if (status === "failed") return "bad";
 return "idle";
}
