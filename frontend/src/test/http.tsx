import { vi } from "vitest";
import { render } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import type { ReactNode } from "react";
import { OperatorProvider } from "@/operator";
export const person = "10000000-0000-4000-8000-000000000001";
export const people = [{ id: person, name: "Camille Martin", email: "camille@example.test", role: "IT" }, { id: "10000000-0000-4000-8000-000000000009", name: "Alex Dupont", email: "alex@example.test", role: null }];
export type Call = { method: string; path: string; body?: unknown };
export type Handler = (call: Call) => Response | Promise<Response> | undefined;
export function stubHttp(handler: Handler) {
 const calls: Call[] = [];
 vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
  const request = input instanceof Request ? input : new Request(new URL(String(input), window.location.origin), init);
  const text = request.method === "GET" ? "" : await request.text();
  const call: Call = { method: request.method, path: new URL(request.url).pathname, ...(text ? { body: JSON.parse(text) as unknown } : {}) };
  calls.push(call);
  const response = await handler(call);
  if (response) return response;
  if (call.path === "/api/people") return Response.json(people);
  return Response.json({ detail: "Not found" }, { status: 404 });
 }));
 return calls;
}
export function renderWithApi(children: ReactNode, path = "/") {
 const cache = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
 return { cache, ...render(<QueryClientProvider client={cache}><OperatorProvider><MemoryRouter initialEntries={[path]}>{children}</MemoryRouter></OperatorProvider></QueryClientProvider>) };
}
