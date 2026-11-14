import { useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import type { components } from "@/api/schema";
import { useSettings, useUpdateSettings, useAgentStatus, useToggleAgent } from "@/api/hooks";
import { apiErrorKey } from "@/api/errors";
import { useSseEnabled, setSseEnabled } from "@/preferences";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
type Settings = components["schemas"]["Settings-Input"];
function validOrigin(value: string) {
 return /^https?:\/\/(?:localhost|(?:[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?)|\[[a-f0-9:]+\])(?::(?:\*|[0-9]{1,5}))?$/i.test(value) && !value.includes("..");
}
function ListEditor({ kind, values, change }: { kind: "emails" | "origins"; values: string[]; change: (values: string[]) => void }) {
 const { t } = useTranslation("settings");
 const [draft, setDraft] = useState("");
 const valid = kind === "emails" ? /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(draft.trim()) : validOrigin(draft.trim());
 return <fieldset className="space-y-3"><legend className="font-semibold">{t(kind)}</legend><ul className="space-y-2">{values.map(value => <li key={value} className="flex items-center justify-between gap-3"><span className="break-all">{value}</span><Button type="button" variant="outline" aria-label={t("remove", { value })} onClick={() => change(values.filter(item => item !== value))}>{t("removeShort")}</Button></li>)}</ul><label className="block" htmlFor={"add-" + kind}>{t("addValue")}</label><div className="flex gap-2"><Input id={"add-" + kind} value={draft} onChange={e => setDraft(e.target.value)} aria-invalid={!!draft && !valid}/><Button type="button" variant="outline" disabled={!valid || values.includes(draft.trim())} onClick={() => { change([...values, draft.trim()]); setDraft(""); }}>{t("add")}</Button></div>{!!draft && !valid && <p className="text-sm text-red-800">{t("invalid." + kind)}</p>}</fieldset>;
}
function SettingsForm({ initial }: { initial: Settings }) {
 const { t } = useTranslation("settings");
 const [draft, setDraft] = useState(initial), [threshold, setThreshold] = useState(String(initial.auto_send_threshold_eur ?? "0"));
 const update = useUpdateSettings();
 const flagGroups = Object.entries(draft.feature_flags ?? {}).reduce<Record<string, [string, boolean][]>>((groups, entry) => { const priority = entry[0].match(/(?:^|[_ .-])(P[1-3])(?:$|[_ .-])/i)?.[1].toUpperCase() ?? "other"; (groups[priority] ??= []).push(entry); return groups; }, {});
 const validThreshold = /^(?:\d+)(?:\.\d{1,2})?$/.test(threshold) && Number.isFinite(Number(threshold));
 return <form className="space-y-6" onSubmit={e => { e.preventDefault(); if (validThreshold) update.mutate({ ...draft, auto_send_threshold_eur: threshold }, { onSuccess: () => toast.success(t("saved")), onError: error => toast.error(t(apiErrorKey(error))) }); }}>
 <label className="block" htmlFor="auto-threshold">{t("threshold")}</label><Input id="auto-threshold" inputMode="decimal" value={threshold} onChange={e => setThreshold(e.target.value)} aria-invalid={!validThreshold}/>
 <ListEditor kind="emails" values={draft.email_allowlist ?? []} change={value => setDraft({ ...draft, email_allowlist: value })}/>
 <ListEditor kind="origins" values={draft.browser_allowed_origins ?? []} change={value => setDraft({ ...draft, browser_allowed_origins: value })}/>
 <fieldset className="space-y-4"><legend className="font-semibold">{t("flags")}</legend>{!Object.keys(flagGroups).length && <p>{t("noFlags")}</p>}{Object.entries(flagGroups).sort().map(([group, entries]) => <div key={group}><h3 className="mb-2 font-medium">{group === "other" ? t("other") : t("priority", { priority: group })}</h3>{entries.map(([name, enabled]) => <label className="mb-2 flex items-center gap-3" key={name}><Switch checked={enabled} onChange={e => setDraft({ ...draft, feature_flags: { ...draft.feature_flags, [name]: e.target.checked } })}/>{name}</label>)}</div>)}</fieldset>
 {update.isError && <p role="alert" className="text-red-800">{t(apiErrorKey(update.error))}</p>}<Button disabled={update.isPending || !validThreshold}>{t("common:save")}</Button></form>;
}
export default function Settings() {
 const { t } = useTranslation("settings"), query = useSettings(), agent = useAgentStatus(), toggle = useToggleAgent(), sse = useSseEnabled();
 return <div className="space-y-5"><h1 className="text-3xl font-semibold">{t("title")}</h1><Card><h2 className="mb-4 text-xl font-semibold">{t("apiSettings")}</h2>{query.isPending && <p>{t("common:loading")}</p>}{query.isError && <p role="alert">{t(apiErrorKey(query.error))}</p>}{query.data && <SettingsForm key={JSON.stringify(query.data)} initial={query.data}/>}</Card>
 <Card className="space-y-4"><h2 className="text-xl font-semibold">{t("agent")}</h2><p>{t("agentHint")}</p><p>{agent.isError ? t("common:unknown") : agent.data ? t(agent.data.paused ? "common:paused" : "common:running") : t("common:loading")}</p><Button disabled={!agent.data || agent.isError || toggle.isPending} onClick={() => toggle.mutate(!!agent.data?.paused, { onError: error => toast.error(t(apiErrorKey(error))) })}>{t(agent.data?.paused ? "common:resume" : "common:pause")}</Button></Card>
 <Card className="space-y-4"><h2 className="text-xl font-semibold">{t("local")}</h2><label className="flex items-center gap-3"><Switch checked={sse} onChange={e => setSseEnabled(e.target.checked)}/>{t("sse")}</label><p className="text-sm text-slate-600">{t("sseHint")}</p></Card></div>;
}
