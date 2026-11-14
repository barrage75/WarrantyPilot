import { afterEach, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { OperatorProvider, SessionBadge } from "@/operator";
import { stubHttp } from "@/test/http";
import "@/i18n";
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
const karim = { id: "97225c38-d686-5d99-a6cf-53e18aa92e8d", name: "Karim Benali", role: "admin" };
function show() {
 const cache = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
 return render(<QueryClientProvider client={cache}><OperatorProvider><SessionBadge/><p>Protected content</p></OperatorProvider></QueryClientProvider>);
}
it("shows the login screen, signs in with person and password, then signs out", async () => {
 let signedIn = false;
 const calls = stubHttp(call => {
  if (call.path === "/api/auth/me") return signedIn ? Response.json({ person_id: karim.id, name: karim.name, role: "admin" }) : Response.json({ detail: "Authentication required" }, { status: 401 });
  if (call.path === "/api/auth/people") return Response.json([karim]);
  if (call.path === "/api/auth/login") { signedIn = true; return Response.json({ person_id: karim.id, name: karim.name, role: "admin" }); }
  if (call.path === "/api/auth/logout") { signedIn = false; return new Response(null, { status: 204 }); }
  return undefined;
 });
 show();
 expect(await screen.findByRole("heading", { name: "Connexion opérateur" })).toBeInTheDocument();
 expect(screen.queryByText("Protected content")).not.toBeInTheDocument();
 await screen.findByRole("option", { name: "Karim Benali · administrateur" });
 await userEvent.selectOptions(screen.getByLabelText("Personne"), karim.id);
 await userEvent.type(screen.getByLabelText("Mot de passe"), "appelia-demo");
 await userEvent.click(screen.getByRole("button", { name: "Se connecter" }));
 expect(await screen.findByText("Protected content")).toBeInTheDocument();
 expect(calls).toContainEqual({ method: "POST", path: "/api/auth/login", body: { person_id: karim.id, password: "appelia-demo" } });
 await userEvent.click(screen.getByRole("button", { name: "Se déconnecter" }));
 await waitFor(() => expect(calls.some(call => call.path === "/api/auth/logout")).toBe(true));
 expect(await screen.findByRole("heading", { name: "Connexion opérateur" })).toBeInTheDocument();
});
it("reports invalid credentials", async () => {
 stubHttp(call => {
  if (call.path === "/api/auth/me") return Response.json({ detail: "Authentication required" }, { status: 401 });
  if (call.path === "/api/auth/people") return Response.json([karim]);
  if (call.path === "/api/auth/login") return Response.json({ detail: "Invalid credentials" }, { status: 401 });
  return undefined;
 });
 show();
 await screen.findByRole("option", { name: "Karim Benali · administrateur" });
 await userEvent.selectOptions(screen.getByLabelText("Personne"), karim.id);
 await userEvent.type(screen.getByLabelText("Mot de passe"), "wrong");
 await userEvent.click(screen.getByRole("button", { name: "Se connecter" }));
 expect(await screen.findByRole("alert")).toHaveTextContent("Identifiants invalides.");
});
