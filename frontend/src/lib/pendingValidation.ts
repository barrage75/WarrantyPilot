type Entry = { timer: ReturnType<typeof setTimeout> | null };
const pending = new Map<string, Entry>();
const listeners = new Set<() => void>();
const emit = () => listeners.forEach(listener => listener());

export const VALIDATION_DELAY_MS = 5000;
export function subscribeValidation(listener: () => void) {
 listeners.add(listener);
 return () => { listeners.delete(listener); };
}
export const isValidationPending = (caseId: string) => pending.has(caseId);

export function resetPendingValidations() {
 for (const entry of pending.values()) if (entry.timer) clearTimeout(entry.timer);
 pending.clear();
 emit();
}

export function cancelValidation(caseId: string) {
 const entry = pending.get(caseId);
 if (!entry?.timer) return false;
 clearTimeout(entry.timer);
 pending.delete(caseId);
 emit();
 return true;
}

export function queueValidation(caseId: string, send: () => Promise<unknown>, onError: (error: unknown) => void) {
 if (pending.has(caseId)) return false;
 const entry: Entry = { timer: null };
 entry.timer = setTimeout(() => {
  entry.timer = null;
  void Promise.resolve().then(send).catch(onError).finally(() => {
   pending.delete(caseId);
   emit();
  });
 }, VALIDATION_DELAY_MS);
 pending.set(caseId, entry);
 emit();
 return true;
}

// Never persist or flush queued approvals when leaving the document.
window.addEventListener("pagehide", () => {
 for (const caseId of pending.keys()) cancelValidation(caseId);
});
