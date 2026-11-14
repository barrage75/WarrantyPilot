import { expect, it } from "vitest";
import { mergeEvents } from "./useCaseStream";
import type { StreamEventLocal } from "./untyped";
const event = (seq: number): StreamEventLocal => ({ seq, at: "", actor: "system", type: "case_created", payload: {}, hash: "" });
it("merges history and stream in sequence without duplicates", () => expect(mergeEvents([event(3), event(1)], [event(2), event(3)]).map(e => e.seq)).toEqual([1, 2, 3]));
it("accepts empty history", () => expect(mergeEvents([], [])).toEqual([]));
