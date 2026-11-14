import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, screen } from "@testing-library/react";
import { Toaster } from "sonner";
import { Link, Route, Routes } from "react-router-dom";
import { renderWithApi, stubHttp, type Call } from "@/test/http";
import { resetPendingValidations } from "@/lib/pendingValidation";
import i18n from "@/i18n";
import { PendingValidationButton } from "./PendingValidationButton";
let calls: Call[];
beforeEach(async () => {
 await i18n.changeLanguage("fr");
 resetPendingValidations();
 calls = stubHttp(call => call.path.endsWith("/validate") ? Response.json({ status: "sending" }) : undefined);
});
afterEach(() => { cleanup(); resetPendingValidations(); vi.useRealTimers(); vi.unstubAllGlobals(); });
function show() {
 return renderWithApi(<><Toaster/><Routes><Route path="/" element={<><PendingValidationButton caseId="case"/><Link to="/away">away</Link></>}/><Route path="/away" element={<p>other page</p>}/></Routes></>);
}
it("keeps the delayed POST alive after navigating away", async () => {
 show();
 vi.useFakeTimers();
 fireEvent.click(screen.getByRole("button", { name: "Valider" }));
 fireEvent.click(screen.getByRole("link", { name: "away" }));
 expect(calls).toEqual([]);
 await act(async () => { await vi.advanceTimersByTimeAsync(5000); await vi.runOnlyPendingTimersAsync(); });
 expect(calls).toEqual([{ method: "POST", path: "/api/cases/case/validate", body: {} }]);
});
it("lets Sonner undo a queued validation after navigation", async () => {
 show();
 vi.useFakeTimers();
 fireEvent.click(screen.getByRole("button", { name: "Valider" }));
 fireEvent.click(screen.getByRole("link", { name: "away" }));
 await act(async () => { await vi.advanceTimersByTimeAsync(1); });
 fireEvent.click(screen.getByRole("button", { name: "Annuler" }));
 await act(async () => { await vi.advanceTimersByTimeAsync(10000); });
 expect(calls).toEqual([]);
});
