import { useSyncExternalStore } from "react";
const key = "wp-sse-enabled";
const event = "wp-preferences";
function read() { try { return localStorage.getItem(key) === "true"; } catch { return false; } }
function subscribe(callback: () => void) {
 window.addEventListener(event, callback);
 window.addEventListener("storage", callback);
 return () => { window.removeEventListener(event, callback); window.removeEventListener("storage", callback); };
}
export function setSseEnabled(value: boolean) {
 try { localStorage.setItem(key, String(value)); } catch { return; }
 window.dispatchEvent(new Event(event));
}
export const useSseEnabled = () => useSyncExternalStore(subscribe, read, () => false);
