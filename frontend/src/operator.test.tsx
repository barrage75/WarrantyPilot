import { afterEach, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { OperatorProvider, SessionBadge } from "@/operator";
import { stubHttp } from "@/test/http";
import "@/i18n";
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
const samy = { id: "0366886f-898d-51be-87ad-2cb539f58c9a", name: "Samy Benzeguir", role: "admin" };
function show() {
 const cache = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
 return render(<QueryClientProvider client={cache}><OperatorProvider><SessionBadge/><p>Protected content</p></OperatorProvider></QueryClientProvider>);
}
it("shows the login screen, signs in with person and password, then signs out", async () => {
 let signedIn = false;
 const calls = stubHttp(call => {
  if (call.path === "/api/auth/me") return signedIn ? Response.json({ person_id: samy.id, name: samy.name, role: "admin" }) : Response.json({ detail: "Authentication required" }, { status: 401 });
  if (call.path === "/api/auth/people") return Response.json([samy]);
  if (call.path === "/api/auth/login") { signedIn = true; return Response.json({ person_id: samy.id, name: samy.name, role: "admin" }); }
  if (call.path === "/api/auth/logout") { signedIn = false; return new Response(null, { status: 204 }); }
  return undefined;
 });
 show();
 expect(await screen.findByRole("heading", { name: "Connexion opérateur" })).toBeInTheDocument();
 expect(screen.queryByText("Protected content")).not.toBeInTheDocument();
 await screen.findByRole("option", { name: "Samy Benzeguir · administrateur" });
 await userEvent.selectOptions(screen.getByLabelText("Personne"), samy.id);
 await userEvent.type(screen.getByLabelText("Mot de passe"), "nimportequoi");
 await userEvent.click(screen.getByRole("button", { name: "Se connecter" }));
 expect(await screen.findByText("Protected content")).toBeInTheDocument();
 expect(calls).toContainEqual({ method: "POST", path: "/api/auth/login", body: { person_id: samy.id, password: "nimportequoi" } });
 await userEvent.click(screen.getByRole("button", { name: "Se déconnecter" }));
 await waitFor(() => expect(calls.some(call => call.path === "/api/auth/logout")).toBe(true));
 expect(await screen.findByRole("heading", { name: "Connexion opérateur" })).toBeInTheDocument();
});
it("allows login with an empty demo password", async () => {
 let signedIn = false;
 const calls = stubHttp(call => {
  if (call.path === "/api/auth/me") return signedIn ? Response.json({ person_id: samy.id, name: samy.name, role: "admin" }) : Response.json({ detail: "Authentication required" }, { status: 401 });
  if (call.path === "/api/auth/people") return Response.json([samy]);
  if (call.path === "/api/auth/login") { signedIn = true; return Response.json({ person_id: samy.id, name: samy.name, role: "admin" }); }
  return undefined;
 });
 show();
 await screen.findByRole("option", { name: "Samy Benzeguir · administrateur" });
 await userEvent.selectOptions(screen.getByLabelText("Personne"), samy.id);
 expect(screen.getByRole("button", { name: "Se connecter" })).toBeEnabled();
 expect(screen.getByLabelText("Mot de passe")).not.toBeRequired();
 await userEvent.click(screen.getByRole("button", { name: "Se connecter" }));
 expect(await screen.findByText("Protected content")).toBeInTheDocument();
 expect(calls).toContainEqual({ method: "POST", path: "/api/auth/login", body: { person_id: samy.id, password: "" } });
});
it("reports invalid credentials", async () => {
 stubHttp(call => {
  if (call.path === "/api/auth/me") return Response.json({ detail: "Authentication required" }, { status: 401 });
  if (call.path === "/api/auth/people") return Response.json([samy]);
  if (call.path === "/api/auth/login") return Response.json({ detail: "Invalid credentials" }, { status: 401 });
  return undefined;
 });
 show();
 await screen.findByRole("option", { name: "Samy Benzeguir · administrateur" });
 await userEvent.selectOptions(screen.getByLabelText("Personne"), samy.id);
 await userEvent.type(screen.getByLabelText("Mot de passe"), "wrong");
 await userEvent.click(screen.getByRole("button", { name: "Se connecter" }));
 expect(await screen.findByRole("alert")).toHaveTextContent("Identifiants invalides.");
});
