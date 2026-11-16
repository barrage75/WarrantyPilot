import { useId, useState, type FormEvent, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { LogOut, ShieldCheck } from "lucide-react";
import { ApiError, localRequest } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import heroImage from "@/assets/iso/hero.webp";
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
 function submit(event: FormEvent) { event.preventDefault(); setFailed(false); if (personId) login.mutate(); }
 return <main className="flex min-h-screen items-center justify-center bg-canvas p-4 sm:p-6"><Card className="w-full max-w-2xl space-y-5">
  <header className="text-center">
   <span className="mx-auto mb-3 grid h-12 w-12 place-items-center rounded-2xl bg-accent text-white"><ShieldCheck size={26}/></span>
   <p className="text-lg font-bold">{t("product")}</p><h1 className="mt-3 text-2xl font-semibold">{t("loginTitle")}</h1>
   <p className="mx-auto mt-2 max-w-md text-sm text-muted">{t("loginHelp")}</p>
   <img src={heroImage} alt="" aria-hidden="true" className="mx-auto mt-3 hidden h-36 w-full max-w-sm object-contain sm:block"/>
  </header>
  <form className="space-y-3" onSubmit={submit}>
   <label htmlFor={personField} className="block font-medium">{t("operator")}</label>
   <select id={personField} className="block min-h-10 w-full rounded-xl border border-line bg-surface px-3 py-2" disabled={!people.data} value={personId} onChange={event => setPersonId(event.target.value)} required>
    <option value="">{t(people.isPending ? "loading" : "choosePerson")}</option>
    {people.data?.map(person => <option key={person.id} value={person.id}>{person.name} · {t("roles." + person.role)}</option>)}
   </select>
   <label htmlFor={passwordField} className="block font-medium">{t("password")}</label>
   <input id={passwordField} type="password" autoComplete="current-password" className="block min-h-10 w-full rounded-xl border border-line px-3 py-2" value={password} onChange={event => setPassword(event.target.value)}/>
   {people.isError && <p role="alert" className="text-bad">{t("peopleError")}</p>}
   {failed && <p role="alert" className="text-bad">{t("loginFailed")}</p>}
   <Button disabled={!personId || login.isPending}>{t("login")}</Button>
  </form>
 </Card></main>;
}
export function SessionBadge() {
 const { t } = useTranslation("common");
 const { user, logout } = useOperator();
 if (!user) return null;
 return <div className="flex flex-wrap items-center gap-3 text-sm"><span role="status">{t("operatorActive", { name: user.name })} · {t("roles." + user.role)}</span><Button variant="outline" onClick={logout}><LogOut size={16}/>{t("logout")}</Button></div>;
}
