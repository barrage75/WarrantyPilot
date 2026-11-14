import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ArrowUp, Bot, ChevronRight, MessageCircle, ShieldCheck } from "lucide-react";
import { useTranslation } from "react-i18next";
import { sendChatMessage, startConversation, type ChatConversation, type ChatReply } from "@/api/resources";
import { apiErrorKey } from "@/api/errors";
import { useOperator } from "@/operator-state";
import { Button } from "@/components/ui/button";
import { Tile } from "@/components/bento/Tile";
import { Textarea } from "@/components/ui/textarea";
export default function Chat() {
 const { t } = useTranslation("chat");
 const { personId } = useOperator();
 const [params] = useSearchParams();
 const prefilled = params.get("message") ?? "";
 const composer = useRef<HTMLTextAreaElement>(null);
 const logEnd = useRef<HTMLDivElement>(null);
 const [conversation, setConversation] = useState<ChatConversation>(), [text, setText] = useState(prefilled), [reply, setReply] = useState<ChatReply>(), [busy, setBusy] = useState(false), [error, setError] = useState<unknown>();
 useEffect(() => { setText(prefilled); }, [prefilled]);
 useEffect(() => { let active = true; startConversation().then(value => { if (active) setConversation(value); }).catch((reason: unknown) => { if (active) setError(reason ?? true); }); return () => { active = false; }; }, []);
 useEffect(() => { logEnd.current?.scrollIntoView?.({ block: "nearest" }); }, [conversation?.messages.length]);
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
 return <div className="mx-auto min-w-0 max-w-4xl space-y-6"><header><h1 className="text-4xl font-bold tracking-tight">{t("title")}</h1><p className="mt-2 text-ink/70">{t("subtitle")}</p></header><Tile className="min-w-0 space-y-5 p-5 hover:translate-y-0 hover:shadow-none sm:p-8">
 {conversation && <p role="note" aria-label={t("aiNotice")} className="flex items-start gap-3 rounded-2xl bg-accent/5 p-4 text-sm text-indigo-950"><ShieldCheck className="mt-0.5 shrink-0 text-indigo-700" size={20} strokeWidth={1.75} aria-hidden="true"/>{conversation.disclosure_text}</p>}
 {conversation && <div role="log" aria-live="polite" aria-label={t("conversation")} className="max-h-[55vh] space-y-5 overflow-y-auto overscroll-contain p-1">{conversation.messages.map(message => <div key={message.id} className={`flex items-start gap-3 ${message.role === "human" ? "flex-row-reverse" : ""}`}><span aria-hidden="true" className={`grid h-9 w-9 shrink-0 place-items-center rounded-full ${message.role === "human" ? "bg-canvas text-ink" : "bg-ink text-white"}`}>{message.role === "human" ? <MessageCircle size={18} strokeWidth={1.75}/> : <Bot size={18} strokeWidth={1.75}/>}</span><div className={`min-w-0 max-w-[85%] rounded-[22px] p-4 ${message.role === "human" ? "rounded-tr-md bg-ink text-white" : "rounded-tl-md bg-canvas"}`}><p className={`mb-1 text-xs font-semibold ${message.role === "human" ? "text-zinc-300" : "text-ink/70"}`}>{t(message.role)}</p><p className="whitespace-pre-wrap text-sm leading-relaxed [overflow-wrap:anywhere]">{message.textKey ? t(message.textKey, { defaultValue: message.textKey }) : message.text}</p></div></div>)}<div ref={logEnd}/></div>}
 {!conversation && !error && <p role="status">{t("common:loading")}</p>}
 {equipment && <p className="rounded-2xl bg-ok/10 p-4 text-sm font-medium text-emerald-900 [overflow-wrap:anywhere]">{t("equipment", { equipment })}</p>}
 {questions.length > 0 && <div className="rounded-2xl bg-warn/10 p-4 text-amber-950"><h2 className="font-semibold">{t("clarification")}</h2><ul className="mt-2 list-disc space-y-1 pl-5 text-sm [overflow-wrap:anywhere]">{questions.map(question => <li key={question}>{question}</li>)}</ul></div>}
 {reply?.case_id && <p><Link className="inline-flex min-h-10 items-center gap-2 rounded-full bg-ink px-5 py-2 text-sm font-semibold text-white" to={"/cases/" + reply.case_id}>{t("viewCase", { id: reply.case_id.slice(0, 8) })}<ChevronRight size={16} aria-hidden="true"/></Link></p>}
 {error !== undefined && <p role="alert" className="my-3 text-red-800">{t(apiErrorKey(error))}</p>}
 {!personId && <p className="mt-4 text-sm text-amber-900">{t("common:identityRequired")}</p>}
 {conversation && !conversation.messages.some(message => message.role === "human") && <div role="group" aria-label={t("suggestions")} className="flex flex-wrap gap-2">{["power", "charging", "connection"].map(key => <button type="button" key={key} className="min-h-10 max-w-full rounded-full border border-line px-4 py-2 text-left text-sm text-ink hover:bg-canvas" onClick={() => { setText(t("prompts." + key)); composer.current?.focus(); }}>{t("suggestionLabels." + key)}</button>)}</div>}
 <form className="space-y-3 border-t border-line pt-5" onSubmit={event => { event.preventDefault(); void send(); }}><label className="block font-medium" htmlFor="chat-message">{t("message")}</label><Textarea ref={composer} className="min-h-28 resize-y bg-canvas/60" id="chat-message" placeholder={t("placeholder")} value={text} onChange={e => setText(e.target.value)} required/><div className="flex flex-wrap items-center justify-between gap-3"><p className="max-w-sm text-xs text-muted">{t("messageHelp")}</p><Button disabled={!conversation || !personId || busy || !text.trim()}>{t(busy ? "sending" : "send")}<ArrowUp size={16} aria-hidden="true"/></Button></div></form></Tile></div>;
}
