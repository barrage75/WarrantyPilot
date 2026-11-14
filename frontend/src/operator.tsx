import { useId, useState, type FormEvent, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { LogOut, ShieldCheck } from "lucide-react";
import { ApiError, localRequest } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { OperatorContext, useOperator, type SessionUser } from "./operator-state";
type LoginPerson = { id: string; name: string; role: "admin" | "operator" };
async function fetchMe(): Promise<SessionUser | null> {
 try { return await localRequest<SessionUser>("/auth/me"); } catch (error) { if (error instanceof ApiError && error.status === 401) return null; throw error; }
}
export function OperatorProvider({ children }: { children: ReactNode }) {
 const cache = useQueryClient();
 const me = useQuery({ queryKey: ["auth", "me"], queryFn: fetchMe, staleTime: 60000, retry: false });
 const logout = useMutation({ mutationFn: () => localRequest<unknown>("/auth/logout", "POST").catch(() => undefined), onSettled: () => { cache.clear(); void cache.invalidateQueries({ queryKey: ["auth", "me"] }); } });
 const { t } = useTranslation("common");
 if (me.isPending) return <p role="status" className="p-6">{t("loading")}</p>;
 const user = me.data ?? null;
 if (!user) return <LoginScreen/>;
 return <OperatorContext.Provider value={{ user, personId: user.person_id, isAdmin: user.role === "admin", logout: () => logout.mutate() }}>{children}</OperatorContext.Provider>;
}
export function LoginScreen() {
 const { t } = useTranslation("common");
 const cache = useQueryClient();
 const personField = useId(), passwordField = useId();
 const people = useQuery({ queryKey: ["auth", "people"], queryFn: () => localRequest<LoginPerson[]>("/auth/people"), retry: false });
 const [personId, setPersonId] = useState(""), [password, setPassword] = useState(""), [failed, setFailed] = useState(false);
 const login = useMutation({ mutationFn: () => localRequest<SessionUser>("/auth/login", "POST", { person_id: personId, password }), onSuccess: user => { setPassword(""); cache.setQueryData(["auth", "me"], user); }, onError: () => setFailed(true) });
 function submit(event: FormEvent) { event.preventDefault(); setFailed(false); if (personId && password) login.mutate(); }
 return <main className="flex min-h-screen items-center justify-center bg-slate-100 p-6"><Card className="w-full max-w-md space-y-4">
  <h1 className="flex items-center gap-2 text-2xl font-semibold"><ShieldCheck className="text-teal-700"/>{t("loginTitle")}</h1>
  <p className="text-sm text-slate-600">{t("loginHelp")}</p>
  <form className="space-y-3" onSubmit={submit}>
   <label htmlFor={personField} className="block font-medium">{t("operator")}</label>
   <select id={personField} className="block w-full rounded-md border border-slate-300 bg-white p-2" disabled={!people.data} value={personId} onChange={event => setPersonId(event.target.value)} required>
    <option value="">{t(people.isPending ? "loading" : "choosePerson")}</option>
    {people.data?.map(person => <option key={person.id} value={person.id}>{person.name} · {t("roles." + person.role)}</option>)}
   </select>
   <label htmlFor={passwordField} className="block font-medium">{t("password")}</label>
   <input id={passwordField} type="password" autoComplete="current-password" className="block w-full rounded-md border border-slate-300 p-2" value={password} onChange={event => setPassword(event.target.value)} required/>
   {people.isError && <p role="alert" className="text-red-800">{t("peopleError")}</p>}
   {failed && <p role="alert" className="text-red-800">{t("loginFailed")}</p>}
   <Button disabled={!personId || !password || login.isPending}>{t("login")}</Button>
  </form>
 </Card></main>;
}
export function SessionBadge() {
 const { t } = useTranslation("common");
 const { user, logout } = useOperator();
 if (!user) return null;
 return <div className="flex flex-wrap items-center gap-3 text-sm"><span role="status">{t("operatorActive", { name: user.name })} · {t("roles." + user.role)}</span><Button variant="outline" onClick={logout}><LogOut size={16}/>{t("logout")}</Button></div>;
}
