import { useState, type ReactNode } from "react";
import { motion, useReducedMotion } from "motion/react";
import { Bot, Coins, Globe, Mail, Radio, SlidersHorizontal, type LucideIcon } from "lucide-react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import type { components } from "@/api/schema";
import { useSettings, useUpdateSettings, useAgentStatus, useToggleAgent } from "@/api/hooks";
import { apiErrorKey } from "@/api/errors";
import { useSseEnabled, setSseEnabled } from "@/preferences";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tile } from "@/components/bento/Tile";
import { StatusDot } from "@/components/bento/StatusDot";
import { Switch } from "@/components/ui/switch";
type Settings = components["schemas"]["Settings-Input"];
function SettingsTile({ title, hint, icon: Icon, children }: { title: string; hint: string; icon: LucideIcon; children: ReactNode }) {
 const reduced = useReducedMotion();
 return <motion.div className="min-w-0" initial={reduced ? false : { opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: reduced ? 0 : 0.25 }}><Tile className="h-full min-w-0 space-y-5" aria-label={title}><header className="space-y-3"><span className="inline-flex rounded-2xl bg-canvas p-3"><Icon size={28} strokeWidth={1.75} aria-hidden="true"/></span><h2 className="text-xl font-bold tracking-tight">{title}</h2><p className="text-sm leading-relaxed text-ink">{hint}</p></header>{children}</Tile></motion.div>;
}
function validOrigin(value: string) {
 return /^https?:\/\/(?:localhost|(?:[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?)|\[[a-f0-9:]+\])(?::(?:\*|[0-9]{1,5}))?$/i.test(value) && !value.includes("..");
}
function ListEditor({ kind, values, change }: { kind: "emails" | "origins"; values: string[]; change: (values: string[]) => void }) {
 const { t } = useTranslation("settings");
 const [draft, setDraft] = useState("");
 const valid = kind === "emails" ? /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(draft.trim()) : validOrigin(draft.trim());
 return <SettingsTile title={t(kind)} hint={t(kind + "Hint")} icon={kind === "emails" ? Mail : Globe}><fieldset className="min-w-0 space-y-3"><legend className="sr-only">{t(kind)}</legend><ul className="space-y-2">{values.map(value => <li key={value} className="flex flex-wrap items-center justify-between gap-3"><span className="min-w-0 break-all text-sm">{value}</span><Button type="button" variant="outline" aria-label={t("remove", { value })} onClick={() => change(values.filter(item => item !== value))}>{t("removeShort")}</Button></li>)}</ul><label className="block text-sm font-medium" htmlFor={"add-" + kind}>{t("addValue")}</label><div className="flex flex-wrap gap-2"><Input className="min-w-0 flex-1 basis-40" id={"add-" + kind} value={draft} onChange={e => setDraft(e.target.value)} aria-invalid={!!draft && !valid} aria-describedby={!!draft && !valid ? "invalid-" + kind : undefined}/><Button type="button" variant="outline" disabled={!valid || values.includes(draft.trim())} onClick={() => { change([...values, draft.trim()]); setDraft(""); }}>{t("add")}</Button></div>{!!draft && !valid && <p id={"invalid-" + kind} className="text-sm text-red-800">{t("invalid." + kind)}</p>}</fieldset></SettingsTile>;
}
function SettingsForm({ initial }: { initial: Settings }) {
 const { t } = useTranslation("settings");
 const [draft, setDraft] = useState(initial), [threshold, setThreshold] = useState(String(initial.auto_send_threshold_eur ?? "0"));
 const update = useUpdateSettings();
 const flagGroups = Object.entries(draft.feature_flags ?? {}).reduce<Record<string, [string, boolean][]>>((groups, entry) => { const priority = entry[0].match(/(?:^|[_ .-])(P[1-3])(?:$|[_ .-])/i)?.[1].toUpperCase() ?? "other"; (groups[priority] ??= []).push(entry); return groups; }, {});
 const validThreshold = /^(?:\d+)(?:\.\d{1,2})?$/.test(threshold) && Number.isFinite(Number(threshold));
 return <form className="space-y-4" onSubmit={e => { e.preventDefault(); if (validThreshold) update.mutate({ ...draft, auto_send_threshold_eur: threshold }, { onSuccess: () => toast.success(t("saved")), onError: error => toast.error(t(apiErrorKey(error))) }); }}><div className="grid grid-cols-1 items-start gap-4 md:grid-cols-2"><div className="min-w-0 space-y-4">
 <SettingsTile title={t("thresholdTitle")} hint={t("thresholdHint")} icon={Coins}><label className="block text-sm font-medium" htmlFor="auto-threshold">{t("threshold")}</label><Input id="auto-threshold" inputMode="decimal" value={threshold} onChange={e => setThreshold(e.target.value)} aria-invalid={!validThreshold} aria-describedby={!validThreshold ? "invalid-threshold" : undefined}/>{!validThreshold && <p id="invalid-threshold" className="text-sm text-red-800">{t("invalid.threshold")}</p>}</SettingsTile>
 <SettingsTile title={t("flags")} hint={t("flagsHint")} icon={SlidersHorizontal}><fieldset className="space-y-4"><legend className="sr-only">{t("flags")}</legend>{!Object.keys(flagGroups).length && <p>{t("noFlags")}</p>}{Object.entries(flagGroups).sort().map(([group, entries]) => <div key={group}><h3 className="mb-2 font-medium">{group === "other" ? t("other") : t("priority", { priority: group })}</h3>{entries.map(([name, enabled]) => <label className="mb-2 flex min-h-10 items-center gap-3 [overflow-wrap:anywhere]" key={name}><Switch checked={enabled} onChange={e => setDraft({ ...draft, feature_flags: { ...draft.feature_flags, [name]: e.target.checked } })}/>{name}</label>)}</div>)}</fieldset></SettingsTile>
 </div><div className="min-w-0 space-y-4"><ListEditor kind="emails" values={draft.email_allowlist ?? []} change={value => setDraft({ ...draft, email_allowlist: value })}/><ListEditor kind="origins" values={draft.browser_allowed_origins ?? []} change={value => setDraft({ ...draft, browser_allowed_origins: value })}/></div></div>
 <div className="flex flex-wrap items-center gap-4">{update.isError && <p role="alert" className="w-full text-red-800">{t(apiErrorKey(update.error))}</p>}<Button disabled={update.isPending || !validThreshold}>{t("common:save")}</Button>{update.isPending && <p role="status">{t("saving")}</p>}</div></form>;
}
export default function Settings() {
 const { t } = useTranslation("settings"), query = useSettings(), agent = useAgentStatus(), toggle = useToggleAgent(), sse = useSseEnabled();
 return <div className="space-y-6 text-ink"><header className="space-y-3"><h1 className="text-4xl font-bold tracking-tight">{t("title")}</h1><p>{t("apiSettings")}</p></header>{query.isPending && <p>{t("common:loading")}</p>}{query.isError && <Tile><p role="alert">{t(apiErrorKey(query.error))}</p></Tile>}{query.data && <SettingsForm key={JSON.stringify(query.data)} initial={query.data}/>}
 <div className="grid grid-cols-1 gap-4 md:grid-cols-2"><SettingsTile title={t("agent")} hint={t("agentHint")} icon={Bot}><p className="flex items-center gap-2"><StatusDot tone={agent.isError || !agent.data ? "idle" : agent.data.paused ? "waiting" : "ok"}/>{agent.isError ? t("common:unknown") : agent.data ? t(agent.data.paused ? "common:paused" : "common:running") : t("common:loading")}</p><Button disabled={!agent.data || agent.isError || toggle.isPending} onClick={() => toggle.mutate(!!agent.data?.paused, { onError: error => toast.error(t(apiErrorKey(error))) })}>{t(agent.data?.paused ? "common:resume" : "common:pause")}</Button></SettingsTile>
 <SettingsTile title={t("local")} hint={t("sseHint")} icon={Radio}><label className="flex min-h-10 items-center gap-3"><Switch checked={sse} onChange={e => setSseEnabled(e.target.checked)}/>{t("sse")}</label></SettingsTile></div></div>;
}
