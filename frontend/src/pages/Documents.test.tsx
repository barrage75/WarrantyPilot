import { File as NodeFile } from "node:buffer";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import Documents from "./Documents";
import i18n, { resources } from "@/i18n";
import { people, renderWithApi } from "@/test/http";

const item = { id: "doc-1", name: "facture.pdf", source: "facturx", state: "extracted", suspicious: false, facts_count: 2, created_at: null };
let calls: { path: string; method: string; body?: FormData | null }[];
let uploadResult: Record<string, unknown>, serverStatus: number, gate: Promise<void> | undefined;
let total: number, empty: boolean;
let listState: string, listSuspicious: boolean;
beforeEach(async () => {
 const nativeForm = await new Response("--boundary--\r\n", { headers: { "Content-Type": "multipart/form-data; boundary=boundary" } }).formData();
 vi.stubGlobal("FormData", nativeForm.constructor);
 vi.stubGlobal("File", NodeFile);
 await i18n.changeLanguage("fr");
 calls = []; total = 1; empty = false; serverStatus = 200; gate = undefined;
 listState = "extracted"; listSuspicious = false;
 uploadResult = { document_id: item.id, duplicate: false, state: "extracted", facts: 2 };
 vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
  const request = input instanceof Request ? input : new Request(new URL(String(input), window.location.origin), init);
  const url = new URL(request.url);
  const body = request.method === "POST" && url.pathname.endsWith("/upload") ? await request.formData() : null;
  calls.push({ path: url.pathname + url.search, method: request.method, body });
  if (url.pathname === "/api/people") return Response.json(people);
  if (url.pathname === "/api/documents") return Response.json({ items: empty ? [] : [{ ...item, state: listState, suspicious: listSuspicious }], total, limit: 20, offset: Number(url.searchParams.get("offset")) });
  if (url.pathname === "/api/documents/doc-1") return Response.json({ ...item, facts: [{ field: "invoice_number", value: "INV-42", confidence: 1 }, { field: "supplier_name", value: "Appelia", confidence: 1 }, { field: "lines[1].model", value: "Dell Latitude 7440", confidence: 0.9 }] });
  if (url.pathname === "/api/documents/upload") { await gate; return Response.json(serverStatus === 200 ? uploadResult : { detail: "Document invalide" }, { status: serverStatus }); }
  if (url.pathname === "/api/intake/poll") return Response.json({ messages: [{ state: "failure" }, { state: "invoice" }, { state: "invoice" }, { state: "duplicate" }, { state: "quarantined" }, { state: "ignored" }] });
  return Response.json({ detail: "Not found" }, { status: 404 });
 }));
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
async function render() { renderWithApi(<Documents/>, "/documents"); await screen.findByText("facture.pdf"); }
async function upload(name = "invoice.pdf") {
 await userEvent.upload(screen.getByLabelText("Choisir un fichier"), new File(["%PDF-test"], name, { type: "application/pdf" }));
}
it("lists documents with source, state, facts, undated placeholder and pagination", async () => {
 total = 21; await render();
 const row = screen.getByRole("article", { name: /facture.pdf/ });
 expect(row).toHaveTextContent("Factur-X"); expect(row).toHaveTextContent("Extrait");
 expect(within(row).getByText("2")).toBeInTheDocument(); expect(row).toHaveTextContent("—");
 expect(screen.getByRole("button", { name: "Précédent" })).toBeDisabled();
 await userEvent.click(screen.getByRole("button", { name: "Suivant" }));
 await screen.findByText("Page 2");
 await waitFor(() => expect(calls.some(call => call.path.includes("offset=20"))).toBe(true));
 await userEvent.click(screen.getByRole("button", { name: "Précédent" }));
 await screen.findByText("Page 1");
});
it("rejects unsupported extensions and oversize files without any request", async () => {
 await render(); const before = calls.length;
 fireEvent.change(screen.getByLabelText("Choisir un fichier"), { target: { files: [new File(["x"], "evil.exe")] } });
 expect(await screen.findByRole("alert")).toHaveTextContent("Format refusé");
 const large = new File(["x"], "large.xml"); Object.defineProperty(large, "size", { value: 10 * 1024 * 1024 + 1 });
 fireEvent.drop(screen.getByRole("button", { name: /Déposez/ }), { dataTransfer: { files: [large] } });
 expect(await screen.findByRole("alert")).toHaveTextContent("10 Mo");
 expect(calls).toHaveLength(before);
});
it.each([
 ["extracted", "Extrait", "bg-ok/15"],
 ["pending_extraction", "Extraction en attente", "bg-warn/20"],
 ["quarantined", "En quarantaine", "bg-bad/15"],
])("shows %s document state in a tinted pill", async (state, label, tone) => {
 listState = state; listSuspicious = state === "quarantined";
 await render();
 const tile = within(screen.getByRole("article", { name: "facture.pdf" }));
 expect(tile.getByText(label)).toHaveClass(tone);
 if (listSuspicious) expect(tile.getAllByText("Suspect").some(element => element.classList.contains("bg-bad/15"))).toBe(true);
});
it("uploads multipart, announces progress, shows extracted facts and refreshes the list", async () => {
 let finish!: () => void; gate = new Promise<void>(resolve => { finish = resolve; });
 await render(); await upload();
 expect(await screen.findByText("Envoi et analyse du document en cours…")).toHaveAttribute("aria-busy", "true");
 expect(screen.getByRole("progressbar")).not.toHaveAttribute("aria-valuenow");
 expect(screen.queryByLabelText("Terminé")).not.toBeInTheDocument();
 expect(screen.getByText("Envoi").closest("li")).toHaveAttribute("aria-current", "step");
 finish();
 expect(await screen.findByText("2 informations extraites")).toHaveClass("bg-ok/15");
 expect(screen.queryByText("Résultat du dépôt")).not.toBeInTheDocument();
 expect(within(screen.getByTestId("upload-card")).getByText("Voir les faits extraits")).toBeInTheDocument();
 await userEvent.click(await screen.findByText("Voir les faits extraits"));
 expect(await screen.findByText("INV-42")).toBeInTheDocument();
 const sent = calls.find(call => call.path.endsWith("/upload"));
 expect(sent?.method).toBe("POST"); expect((sent?.body?.get("file") as File).name).toBe("invoice.pdf");
 expect(calls.filter(call => call.path.startsWith("/api/documents?")).length).toBe(2);
 expect(screen.queryByRole("progressbar")).not.toBeInTheDocument();
 expect(screen.getAllByLabelText("Terminé")).toHaveLength(3);
});
it("localizes technical Factur-X fields in French and English", async () => {
 await render(); await upload();
 await userEvent.click(await screen.findByText("Voir les faits extraits"));
 expect(await screen.findByText("Nom du fournisseur")).toBeInTheDocument();
 expect(screen.getByText("Ligne 2 · Modèle")).toBeInTheDocument();
 await i18n.changeLanguage("en");
 expect(screen.getByText("Supplier name")).toBeInTheDocument();
 expect(screen.getByText("Line 2 · Model")).toBeInTheDocument();
});
it("shows the exact quarantine warning and pending extraction", async () => {
 uploadResult = { document_id: item.id, duplicate: false, state: "quarantined", facts: 1 };
 await render(); await upload();
 expect(await screen.findByText(/contenu suspect ignoré/)).toBeInTheDocument();
 expect(within(screen.getByTestId("upload-card")).getByText(/Contenu suspect/)).toHaveClass("bg-bad/15");
 expect(screen.getAllByLabelText("Terminé")).toHaveLength(2);
 await waitFor(() => expect(screen.getByLabelText("Choisir un fichier")).not.toBeDisabled());
 uploadResult = { document_id: item.id, duplicate: false, state: "pending_extraction", facts: 0 };
 await upload();
 expect(await screen.findByText("Document enregistré, extraction en attente.")).toBeInTheDocument();
 expect(screen.getAllByLabelText("Terminé")).toHaveLength(2);
});
it("shows duplicate badge and reason with a link to the existing document", async () => {
 uploadResult = { document_id: item.id, duplicate: true, reason: "sha256" };
 await render(); await upload();
 expect(await screen.findByText(/doublon détecté : contenu identique/)).toBeInTheDocument();
 const card = within(screen.getByTestId("upload-card"));
 expect(card.getByText("Doublon — déjà importé")).toHaveClass("bg-warn/20");
 expect(card.getByRole("link", { name: "Voir le document existant" })).toHaveAttribute("href", "/documents?document=doc-1");
 await userEvent.click(card.getByRole("link", { name: "Voir le document existant" }));
 await waitFor(() => expect(screen.getByRole("article", { name: "facture.pdf" })).toHaveClass("ring-accent"));
 expect(await within(screen.getByRole("article", { name: "facture.pdf" })).findByText("INV-42")).toBeVisible();
});
it("shows suspicious reason text on the file card", async () => {
 uploadResult = { document_id: item.id, duplicate: false, state: "quarantined", suspicious: true, reason: "Instructions malveillantes détectées", facts: 0 };
 await render(); await upload();
 expect(await within(screen.getByTestId("upload-card")).findByText("Contenu suspect — Instructions malveillantes détectées")).toHaveClass("bg-bad/15");
});
it("shows zero extracted information without inventing a count", async () => {
 uploadResult.facts = 0;
 await render(); await upload();
 expect(await screen.findByText("0 information extraite")).toHaveClass("bg-ok/15");
});
it("shows an empty document list", async () => {
 empty = true; total = 0; renderWithApi(<Documents/>);
 expect(await screen.findByText("Aucun document enregistré.")).toBeInTheDocument();
});
it.each([false, true])("opens and highlights a linked document (outside first page: %s)", async outside => {
 empty = outside;
 const scroll = vi.fn();
 Object.defineProperty(HTMLElement.prototype, "scrollIntoView", { configurable: true, value: scroll });
 renderWithApi(<Documents/>, "/documents?document=doc-1");
 const tile = await screen.findByRole("article", { name: "facture.pdf" });
 expect(tile).toHaveClass("ring-accent");
 await waitFor(() => expect(within(tile).getByText("INV-42")).toBeVisible());
 expect(within(tile).getByText("Voir les faits extraits").closest("details")).toHaveAttribute("open");
 expect(screen.getAllByRole("article", { name: "facture.pdf" })).toHaveLength(1);
 expect(scroll).toHaveBeenCalled();
});
it("keeps the list usable when a linked document does not exist", async () => {
 renderWithApi(<Documents/>, "/documents?document=unknown");
 expect(await screen.findByText("Ce document est introuvable ou indisponible.")).toBeInTheDocument();
 expect(screen.getByRole("article", { name: "facture.pdf" })).toBeVisible();
 expect(screen.getByRole("button", { name: "Relever la boîte de réception" })).toBeEnabled();
});
it.each([400, 413, 415])("shows server detail for HTTP %s", async status => {
 serverStatus = status; await render(); await upload();
 expect(await screen.findByRole("alert")).toHaveTextContent("Document invalide");
 expect(within(screen.getByTestId("upload-card")).getByRole("alert")).toHaveClass("bg-bad/10");
});
it("polls the inbox, summarises every state, and refreshes", async () => {
 await render(); await userEvent.click(screen.getByRole("button", { name: "Relever la boîte de réception" }));
 expect(await screen.findByText("Factures : 2")).toBeInTheDocument();
 for (const text of ["Signalements : 1", "Doublons : 1", "En quarantaine : 1", "Ignorés : 1"]) expect(screen.getByText(text)).toBeInTheDocument();
 expect(calls.some(call => call.path === "/api/intake/poll" && call.method === "POST")).toBe(true);
 expect(calls.filter(call => call.path.startsWith("/api/documents?")).length).toBe(2);
});
it("supports keyboard activation of the drop zone and regular file input", async () => {
 await render();
 const input = screen.getByLabelText("Choisir un fichier"), click = vi.spyOn(input, "click");
 screen.getByRole("button", { name: /Déposez/ }).focus();
 await userEvent.keyboard("{Enter}"); expect(click).toHaveBeenCalledOnce();
 await userEvent.tab(); expect(input).toHaveFocus();
});
it("registers matching FR/EN namespace keys and renders English", async () => {
 const keys = (value: Record<string, unknown>): string[] => Object.entries(value).flatMap(([key, child]) => typeof child === "object" && child ? keys(child as Record<string, unknown>).map(nested => key + "." + nested) : [key]).sort();
 expect(keys(resources.fr.documents)).toEqual(keys(resources.en.documents));
 await i18n.changeLanguage("en"); renderWithApi(<Documents/>);
 expect(await screen.findByLabelText("Choose a file")).toBeInTheDocument();
 expect(screen.getByRole("button", { name: "Check the inbox" })).toBeInTheDocument();
});
