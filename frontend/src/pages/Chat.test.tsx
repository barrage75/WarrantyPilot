import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { cleanup, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import Chat from "./Chat";
import i18n from "@/i18n";
import { person, renderWithApi, stubHttp, type Call } from "@/test/http";
const disclosure = "Cette conversation est assistée par une intelligence artificielle. Toute décision de garantie reste soumise à validation humaine.";
const englishDisclosure = "This conversation is assisted by artificial intelligence. Every warranty decision remains subject to human validation.";
const caseId = "70245fab-568e-409b-a9d6-ebe52d852249";
const conversation = { id: "c1", conversation_id: "c1", disclosure_text: disclosure, disclosure_key: "aiDisclosure", messages: [{ id: "m0", role: "assistant", text: "Bonjour, décrivez la panne." }] };
let calls: Call[], sends: number, failSend: boolean;
beforeEach(async () => {
 localStorage.clear(); await i18n.changeLanguage("fr"); sends = 0; failSend = false;
 calls = stubHttp(call => {
  if (call.method === "POST" && call.path === "/api/chat/conversations") return Response.json(conversation);
  if (call.method === "POST" && call.path === "/api/chat/conversations/c1/messages") {
   if (failSend) return Response.json({ detail: "down" }, { status: 503 });
   sends += 1; const human = { id: "h" + sends, role: "human", text: (call.body as { text: string }).text };
   if (sends === 1) { const answer = { id: "a1", role: "assistant", text: "Plusieurs équipements correspondent." }; return Response.json({ message: answer, messages: [...conversation.messages, human, answer], case_id: null, clarifying_questions: ["Quel équipement est concerné parmi Jabra Engage 55, Dell Latitude 5440 ?"], questions: [] }); }
   const answer = { id: "a2", role: "assistant", text: "J'ai identifié Dell Latitude 5440 et créé le dossier de garantie.", textKey: "identifiedCreated", textParams: { equipment: "Dell Latitude 5440" } }; return Response.json({ message: answer, messages: [...conversation.messages, human, answer], case_id: caseId, identified_equipment: "Dell Latitude 5440", questions: [] });
  }
  return undefined;
 });
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
it("prefills a URL message without sending until the operator submits", async () => {
 renderWithApi(<Chat/>, "/chat?message=" + encodeURIComponent("Mon Dell ne s’allume plus & chauffe"));
 await screen.findByRole("note");
 expect(screen.getByLabelText("Décrivez votre panne")).toHaveValue("Mon Dell ne s’allume plus & chauffe");
 expect(calls.some(call => call.path.endsWith("/messages"))).toBe(false);
 await userEvent.click(screen.getByRole("button", { name: "Envoyer" }));
 await waitFor(() => expect(calls).toContainEqual({ method: "POST", path: "/api/chat/conversations/c1/messages", body: { text: "Mon Dell ne s’allume plus & chauffe", reporter_id: person } }));
});
it("fills a suggestion as an editable draft without sending", async () => {
 renderWithApi(<Chat/>);
 await screen.findByRole("note");
 await userEvent.click(screen.getByRole("button", { name: "Ne charge plus" }));
 expect(screen.getByLabelText("Décrivez votre panne")).toHaveValue("Mon équipement ne charge plus.");
 expect(screen.getByLabelText("Décrivez votre panne")).toHaveFocus();
 expect(calls.some(call => call.path.endsWith("/messages"))).toBe(false);
});
it("shows the server AI disclosure before the first message, clarifying questions, and links the created case", async () => {
 localStorage.setItem("wp-person-id", person); renderWithApi(<Chat/>);
 expect(await screen.findByRole("note", { name: "Mention IA" })).toHaveTextContent(disclosure);
 expect(screen.getByRole("log")).toHaveTextContent("Bonjour, décrivez la panne.");
 expect(screen.queryByText("SIMULÉ")).not.toBeInTheDocument();
 await userEvent.type(screen.getByLabelText("Décrivez votre panne"), "Mon écran ne s'allume plus");
 await userEvent.click(screen.getByRole("button", { name: "Envoyer" }));
 expect(await screen.findByText(/Quel équipement est concerné/)).toBeInTheDocument();
 expect(screen.getByRole("heading", { name: "Question de clarification" })).toBeInTheDocument();
 expect(calls).toContainEqual({ method: "POST", path: "/api/chat/conversations/c1/messages", body: { text: "Mon écran ne s'allume plus", reporter_id: person } });
 await userEvent.type(screen.getByLabelText("Décrivez votre panne"), "Dell Latitude 5440");
 await userEvent.click(screen.getByRole("button", { name: "Envoyer" }));
 const link = await screen.findByRole("link", { name: "Ouvrir le dossier créé #70245fab" });
 expect(link).toHaveAttribute("href", "/cases/" + caseId);
 expect(screen.getByRole("note")).toHaveTextContent(disclosure);
 expect(screen.queryByText(/Quel équipement est concerné/)).not.toBeInTheDocument();
});
it("requires a selected person before sending (English)", async () => {
 await i18n.changeLanguage("en"); renderWithApi(<Chat/>, "/", null);
 expect(await screen.findByRole("note", { name: "AI disclosure" })).toHaveTextContent(englishDisclosure);
 await userEvent.type(screen.getByLabelText("Describe the fault"), "Broken");
 expect(screen.getByRole("button", { name: "Send" })).toBeDisabled();
 expect(calls.some(call => call.path.endsWith("/messages"))).toBe(false);
});
it("renders keyed identified replies and the AI disclosure in English", async () => {
 localStorage.setItem("wp-person-id", person); await i18n.changeLanguage("en"); renderWithApi(<Chat/>);
 expect(await screen.findByRole("note", { name: "AI disclosure" })).toHaveTextContent(englishDisclosure);
 await userEvent.type(screen.getByLabelText("Describe the fault"), "Mon écran ne s'allume plus");
 await userEvent.click(screen.getByRole("button", { name: "Send" }));
 expect(await screen.findByText(/Quel équipement est concerné/)).toBeInTheDocument();
 await userEvent.type(screen.getByLabelText("Describe the fault"), "Dell Latitude 5440");
 await userEvent.click(screen.getByRole("button", { name: "Send" }));
 expect(await screen.findByText("I identified Dell Latitude 5440 and created the warranty case.")).toBeInTheDocument();
});
it("shows chat API errors and retains the input for retry", async () => {
 localStorage.setItem("wp-person-id", person); failSend = true; renderWithApi(<Chat/>);
 await screen.findByRole("note");
 await userEvent.type(screen.getByLabelText("Décrivez votre panne"), "Panne"); await userEvent.click(screen.getByRole("button", { name: "Envoyer" }));
 expect(await screen.findByRole("alert")).toHaveTextContent("API indisponible");
 expect(screen.getByLabelText("Décrivez votre panne")).toHaveValue("Panne");
});
