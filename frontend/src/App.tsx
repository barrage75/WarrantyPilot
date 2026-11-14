import { lazy, Suspense } from "react";
import { BrowserRouter, NavLink, Route, Routes } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Pause, Play, ShieldCheck } from "lucide-react";
import { Toaster, toast } from "sonner";
import { useAgentStatus, useToggleAgent, useJournal } from "@/api/hooks";
import { Button } from "@/components/ui/button";
import "./i18n";
import { OperatorProvider, OperatorSelector } from "./operator";
const Decisions = lazy(() => import("./pages/Cases").then(module => ({ default: module.Decisions })));
const CasesPage = lazy(() => import("./pages/Cases").then(module => ({ default: module.CasesPage })));
const CaseDetail = lazy(() => import("./pages/Cases").then(module => ({ default: module.CaseDetail })));
const Chat = lazy(() => import("./pages/Chat"));
const Dashboard = lazy(() => import("./pages/Dashboard"));
const PurchaseGuard = lazy(() => import("./pages/PurchaseGuard"));
const Settings = lazy(() => import("./pages/Settings"));
const Demo = lazy(() => import("./pages/Demo"));
const Journal = lazy(() => import("./pages/Journal"));
const pages = [["decisions", "/"], ["cases", "/cases"], ["chat", "/chat"], ["dashboard", "/dashboard"], ["purchaseGuard", "/purchase-guard"], ["settings", "/settings"], ["demo", "/demo"], ["journal", "/journal"]] as const;
function Header() {
 const { t, i18n } = useTranslation();
 const agent = useAgentStatus(), toggle = useToggleAgent(), journal = useJournal();
 const known = !!agent.data && !agent.isError;
 const paused = agent.data?.paused;
 return <header className="grid items-center gap-4 border-b border-slate-200 bg-white px-6 py-4 xl:grid-cols-[minmax(0,1fr)_auto]">
  <p className="text-sm font-medium text-slate-600 xl:col-span-2">{t("workspace")}</p><OperatorSelector/>
  <div className="flex flex-wrap items-center gap-4">
   <span className="flex items-center gap-2 text-sm" role="status"><ShieldCheck size={18}/>{t("journal")} · {journal.isError ? t("unknown") : journal.data ? t(journal.data.ok ? "intact" : "broken") : t("loading")}</span>
   <label className="text-sm">{t("language")} <select className="rounded-md border border-slate-300 p-2" value={i18n.language} onChange={event => void i18n.changeLanguage(event.target.value)}><option value="fr">{t("fr")}</option><option value="en">{t("en")}</option></select></label>
   <div className="flex flex-col items-start gap-1">
    <span className={known ? paused ? "text-xs font-semibold text-red-800" : "text-xs font-semibold text-green-800" : "text-xs text-slate-600"}>{!known ? t("unknown") : t(paused ? "paused" : "running")}</span>
    <Button variant={paused ? "default" : "destructive"} disabled={!known || toggle.isPending} onClick={() => toggle.mutate(!!paused, { onError: () => toast.error(t("error")) })}>{paused ? <Play size={16}/> : <Pause size={16}/>}{t(paused ? "resume" : "pause")}</Button>
   </div>
  </div>
 </header>;
}
export default function App() {
 const { t } = useTranslation();
 return <OperatorProvider><BrowserRouter><div className="min-h-screen lg:grid lg:grid-cols-[240px_1fr]">
 <aside className="bg-slate-950 p-5 text-slate-100"><div className="mb-8 flex items-center gap-3 text-lg font-bold"><ShieldCheck className="text-teal-300"/>{t("product")}</div><nav aria-label={t("navigation")} className="flex flex-wrap gap-1 lg:flex-col">{pages.map(([ns, path]) => <NavLink key={path} to={path} end={path === "/"} className={({ isActive }) => "rounded-lg px-4 py-3 text-sm font-medium " + (isActive ? "bg-teal-800 text-white" : "text-slate-300 hover:bg-slate-800")}>{t(ns + ":title")}</NavLink>)}</nav></aside>
 <div className="min-w-0"><Header/><main className="mx-auto max-w-7xl p-6 lg:p-10"><Suspense fallback={<p role="status">{t("loading")}</p>}><Routes>
 <Route path="/" element={<Decisions/>}/><Route path="/cases" element={<CasesPage/>}/><Route path="/cases/:id" element={<CaseDetail/>}/>
 <Route path="/chat" element={<Chat/>}/><Route path="/dashboard" element={<Dashboard/>}/><Route path="/purchase-guard" element={<PurchaseGuard/>}/>
 <Route path="/settings" element={<Settings/>}/><Route path="/demo" element={<Demo/>}/><Route path="/journal" element={<Journal/>}/>
 <Route path="*" element={<h1>{t("notFound")}</h1>}/></Routes></Suspense></main></div></div><Toaster richColors/></BrowserRouter></OperatorProvider>;
}
