import createClient from "openapi-fetch";
import type { paths } from "./schema";
export const client = createClient<paths>({ baseUrl: window.location.origin, fetch: request => globalThis.fetch(request) });
export class ApiError extends Error {
 constructor(public status: number, public detail: unknown) { super(`API ${status}`); }
}
export async function unwrap<T>(result: { data?: T; error?: unknown; response: Response }): Promise<T> {
 if (!result.response.ok || result.data === undefined) throw new ApiError(result.response.status, result.error);
 return result.data;
}
export async function localRequest<T>(path: string, method = "GET"): Promise<T> {
 const response = await fetch("/api" + path, { method });
 if (!response.ok) throw new ApiError(response.status, await response.text());
 return response.json() as Promise<T>;
}
