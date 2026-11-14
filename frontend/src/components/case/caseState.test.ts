import { expect, it } from "vitest";
import type { components } from "@/api/schema";
import type { StreamEventLocal } from "@/api/untyped";
import { caseTone, journeyStep } from "./caseState";
const item: components["schemas"]["Case"] = { id: "case", incident_id: "incident", status: "prepared", badge: "real", channel: "manual" };
it.each([
 ["prepared", 0, "active"], ["awaiting_validation", 2, "waiting"], ["sending", 3, "active"],
 ["sent", 4, "waiting"], ["failed", 3, "bad"], ["manual_takeover", 3, "idle"],
 ["tracked", 4, "waiting"], ["resolved", 4, "ok"], ["cancelled", 0, "idle"],
] as const)("derives the journey and status dot from %s", (status, step, tone) => {
 expect(journeyStep({ ...item, status }, [])).toBe(step);
 expect(caseTone(status)).toBe(tone);
});
it.each([["verdict_computed", 1], ["policy_decided", 2], ["validated", 3], ["action_started", 3], ["action_succeeded", 4], ["followup_received", 4]] as const)("uses real %s stream events while the case refreshes", (type, step) => {
 const event: StreamEventLocal = { seq: 1, type, at: "2026-11-14T08:00:00Z", actor: "agent", hash: "hash", payload: {} };
 expect(journeyStep(item, [event])).toBe(step);
});
