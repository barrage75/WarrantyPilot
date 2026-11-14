import { createContext, useContext } from "react";
export type SessionUser = { person_id: string; name: string; role: "admin" | "operator"; expires_at?: string | null };
export type SessionState = { user: SessionUser | null; personId: string; isAdmin: boolean; logout: () => void };
export const OperatorContext = createContext<SessionState>({ user: null, personId: "", isAdmin: false, logout: () => undefined });
export const useOperator = () => useContext(OperatorContext);
