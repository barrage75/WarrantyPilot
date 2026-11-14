import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { MockChatApi, type ChatApi, type ChatConversation, type ChatReply } from "@/api/mocks";
import { RealityBadge } from "@/components/Badges";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
const mockApi = new MockChatApi();
export default function Chat({ api = mockApi }: { api?: ChatApi }) {
 const { t } = useTranslation("chat");
 const [conversation, setConversation] = useState<ChatConversation>(), [text, setText] = useState(""), [reply, setReply] = useState<ChatReply>(), [busy, setBusy] = useState(false), [error, setError] = useState(false), [showCase, setShowCase] = useState(false);
 useEffect(() => { let active = true; void api.startConversation().then(value => { if (active) setConversation(value); }).catch(() => { if (active) setError(true); }); return () => { active = false; }; }, [api]);
 async function send() {
  if (!conversation || !text.trim() || busy) return;
  const message = text.trim(); setBusy(true); setError(false);
  try {
   const response = await api.sendMessage(conversation.id, message);
   setConversation(old => old && ({ ...old, messages: [...old.messages, { id: crypto.randomUUID(), role: "human", text: message }, response.message] }));
   setReply(response); setText("");
  } catch { setError(true); } finally { setBusy(false); }
 }
 return <div className="space-y-5"><h1 className="text-3xl font-semibold">{t("title")}</h1><RealityBadge value="simulated" explain/><Card>
 <p className="sticky top-0 z-10 mb-5 rounded-lg border border-teal-300 bg-teal-50 p-4 font-semibold text-teal-950">{t("aiNotice")}</p>
 <div role="log" aria-live="polite" aria-label={t("conversation")} className="space-y-4">{conversation?.messages.map(message => <div key={message.id} className={message.role === "human" ? "ml-8 rounded-lg bg-slate-100 p-4" : "mr-8 rounded-lg bg-teal-50 p-4"}><p className="mb-1 text-xs font-semibold">{t(message.role)}</p><p>{message.textKey ? t(message.textKey) : message.text}</p></div>)}</div>
 {reply?.equipment && <p className="mt-4">{t("equipment", { equipment: reply.equipment })}</p>}
 {reply?.questions?.map(question => <p key={question}>{t(question)}</p>)}
 {reply?.case_id && <div className="my-4"><Button variant="outline" onClick={() => setShowCase(true)}>{t("viewCase")}</Button>{showCase && <p role="status" className="mt-3 text-sm">{t("simulatedCase")}</p>}</div>}
 {error && <p role="alert" className="my-3 text-red-800">{t("common:error")}</p>}
 <form className="mt-6 space-y-3" onSubmit={event => { event.preventDefault(); void send(); }}><label htmlFor="chat-message">{t("message")}</label><Textarea id="chat-message" value={text} onChange={e => setText(e.target.value)} required/><Button disabled={!conversation || busy || !text.trim()}>{t(busy ? "sending" : "send")}</Button></form></Card></div>;
}
