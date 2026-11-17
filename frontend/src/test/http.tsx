import { vi } from "vitest";
import { render } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import type { ReactNode } from "react";
import { OperatorContext, type SessionUser } from "@/operator-state";
export const person = "10000000-0000-4000-8000-000000000001";
export const people = [{ id: person, name: "Camille Martin", email: "camille@example.test", role: "IT" }, { id: "10000000-0000-4000-8000-000000000009", name: "Alex Dupont", email: "alex@example.test", role: null }];
export type Call = { method: string; path: string; search?: string; body?: unknown };
export type Handler = (call: Call) => Response | Promise<Response> | undefined;
export function stubHttp(handler: Handler) {
 const calls: Call[] = [];
 vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
  const request = input instanceof Request ? input : new Request(new URL(String(input), window.location.origin), init);
  const text = request.method === "GET" ? "" : await request.text();
  const url = new URL(request.url);
  const call: Call = { method: request.method, path: url.pathname, ...(url.search ? { search: url.search } : {}), ...(text ? { body: JSON.parse(text) as unknown } : {}) };
  calls.push(call);
  const response = await handler(call);
  if (response) return response;
  if (call.path === "/api/people") return Response.json(people);
  return Response.json({ detail: "Not found" }, { status: 404 });
 }));
 return calls;
}
export const sessionUser: SessionUser = { person_id: "10000000-0000-4000-8000-000000000001", name: "Camille Martin", role: "admin" };
export function TestSession({ children, user = sessionUser }: { children: ReactNode; user?: SessionUser | null }) {
 return <OperatorContext.Provider value={{ user, personId: user?.person_id ?? "", isAdmin: user?.role === "admin", logout: () => undefined }}>{children}</OperatorContext.Provider>;
}
export function renderWithApi(children: ReactNode, path = "/", user: SessionUser | null = sessionUser) {
 const cache = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
 return { cache, ...render(<QueryClientProvider client={cache}><TestSession user={user}><MemoryRouter initialEntries={[path]}>{children}</MemoryRouter></TestSession></QueryClientProvider>) };
}
