import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { sendChatMessage, startConversation, type ChatConversation, type ChatReply } from "@/api/resources";
import { apiErrorKey } from "@/api/errors";
import { useOperator } from "@/operator-state";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
export default function Chat() {
 const { t } = useTranslation("chat");
 const { personId } = useOperator();
 const [conversation, setConversation] = useState<ChatConversation>(), [text, setText] = useState(""), [reply, setReply] = useState<ChatReply>(), [busy, setBusy] = useState(false), [error, setError] = useState<unknown>();
 useEffect(() => { let active = true; startConversation().then(value => { if (active) setConversation(value); }).catch((reason: unknown) => { if (active) setError(reason ?? true); }); return () => { active = false; }; }, []);
 async function send() {
  if (!conversation || !personId || !text.trim() || busy) return;
  setBusy(true); setError(undefined);
  try {
   const response = await sendChatMessage(conversation.id, text.trim(), personId);
   setConversation(old => old && ({ ...old, messages: response.messages }));
   setReply(response); setText("");
  } catch (reason) { setError(reason ?? true); } finally { setBusy(false); }
 }
 const questions = reply?.clarifying_questions?.length ? reply.clarifying_questions : reply?.questions ?? [];
 const equipment = reply?.identified_equipment ?? reply?.equipment;
 return <div className="space-y-5"><h1 className="text-3xl font-semibold">{t("title")}</h1><Card>
 {conversation && <p role="note" aria-label={t("aiNotice")} className="sticky top-0 z-10 mb-5 rounded-lg border border-teal-300 bg-teal-50 p-4 font-semibold text-teal-950">{conversation.disclosure_text}</p>}
 {conversation && <div role="log" aria-live="polite" aria-label={t("conversation")} className="space-y-4">{conversation.messages.map(message => <div key={message.id} className={message.role === "human" ? "ml-8 rounded-lg bg-slate-100 p-4" : "mr-8 rounded-lg bg-teal-50 p-4"}><p className="mb-1 text-xs font-semibold">{t(message.role)}</p><p>{message.textKey ? t(message.textKey, { defaultValue: message.textKey }) : message.text}</p></div>)}</div>}
 {!conversation && !error && <p role="status">{t("common:loading")}</p>}
 {equipment && <p className="mt-4">{t("equipment", { equipment })}</p>}
 {questions.length > 0 && <div className="mt-4 rounded-lg border border-amber-300 bg-amber-50 p-4"><h2 className="font-semibold">{t("clarification")}</h2><ul className="mt-2 list-disc pl-5">{questions.map(question => <li key={question}>{question}</li>)}</ul></div>}
 {reply?.case_id && <p className="my-4"><Link className="font-semibold text-teal-800 underline" to={"/cases/" + reply.case_id}>{t("viewCase", { id: reply.case_id.slice(0, 8) })}</Link></p>}
 {error !== undefined && <p role="alert" className="my-3 text-red-800">{t(apiErrorKey(error))}</p>}
 {!personId && <p className="mt-4 text-sm text-amber-900">{t("common:identityRequired")}</p>}
 <form className="mt-6 space-y-3" onSubmit={event => { event.preventDefault(); void send(); }}><label htmlFor="chat-message">{t("message")}</label><Textarea id="chat-message" value={text} onChange={e => setText(e.target.value)} required/><Button disabled={!conversation || !personId || busy || !text.trim()}>{t(busy ? "sending" : "send")}</Button></form></Card></div>;
}
