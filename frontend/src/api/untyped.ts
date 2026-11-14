// Local response types awaiting explicit backend contracts in OpenAPI.
export interface AgentStatusLocal { paused: boolean }
export interface JournalVerifyLocal { ok: boolean; checked: number; first_bad_seq: number | null; anchors_ok: boolean }
export interface PreflightLocal { ok: boolean; checks: { name: string; ok: boolean; detail: string; fix_hint: string | null }[] }
export interface ResetLocal { status: string }
export interface JournalAnchorLocal { seq: number; hash: string; hmac: string; at: string }
export interface StreamEventLocal {
 seq: number; at: string; actor: string; type: string; payload: Record<string, unknown>; hash: string;
}
