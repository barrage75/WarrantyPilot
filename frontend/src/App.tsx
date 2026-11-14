import { lazy, Suspense } from "react";
import { BrowserRouter, Link, Route, Routes } from "react-router-dom";
import { useTranslation } from "react-i18next";
import * as Popover from "@radix-ui/react-popover";
import { ChevronDown, Pause, Play, ShieldCheck } from "lucide-react";
import { Toaster, toast } from "sonner";
import { useAgentStatus, useToggleAgent, useJournal } from "@/api/hooks";
import { Button } from "@/components/ui/button";
import { NotificationBell, PillNav } from "@/components/bento";
import { CommandPalette } from "@/components/command/CommandPalette";
import "./i18n";
import { OperatorProvider, SessionBadge } from "./operator";
import { useOperator } from "./operator-state";
const Home = lazy(() => import("./pages/Home"));
const Parc = lazy(() => import("./pages/Parc"));
const CasesPage = lazy(() => import("./pages/Cases").then(module => ({ default: module.CasesPage })));
const CaseDetail = lazy(() => import("./pages/Cases").then(module => ({ default: module.CaseDetail })));
const Chat = lazy(() => import("./pages/Chat"));
const Documents = lazy(() => import("./pages/Documents"));
const Dashboard = lazy(() => import("./pages/Dashboard"));
const PurchaseGuard = lazy(() => import("./pages/PurchaseGuard"));
const Settings = lazy(() => import("./pages/Settings"));
const Demo = lazy(() => import("./pages/Demo"));
const Journal = lazy(() => import("./pages/Journal"));
const pages = [["parc", "/parc"], ["home", "/"], ["cases", "/cases"], ["chat", "/chat"], ["documents", "/documents"], ["dashboard", "/dashboard"], ["purchaseGuard", "/purchase-guard"], ["settings", "/settings"], ["demo", "/demo"], ["journal", "/journal"]] as const;
const adminPages = new Set<string>(["/settings", "/demo"]);
function UserMenu() {
 const { t, i18n } = useTranslation();
 const { user } = useOperator();
 const { t: tb } = useTranslation("bento");
 const agent = useAgentStatus(), toggle = useToggleAgent(), journal = useJournal();
 const known = !!agent.data && !agent.isError;
 const paused = agent.data?.paused;
 const firstName = user?.name.split(" ")[0] ?? t("operator");
 return <Popover.Root>
  <Popover.Trigger asChild><Button variant="outline" data-testid="user-menu-trigger" aria-label={tb("userMenu", { name: firstName })}>{firstName}<ChevronDown size={16}/></Button></Popover.Trigger>
  <Popover.Portal><Popover.Content align="end" sideOffset={10} className="z-50 w-[min(22rem,calc(100vw-2rem))] space-y-4 rounded-[28px] bg-surface p-5 text-ink outline-none ring-1 ring-line">
   <SessionBadge/>
   <span className="flex items-center gap-2 text-sm" role="status"><ShieldCheck size={18}/>{t("journal")} · {journal.isError ? t("unknown") : journal.data ? t(journal.data.ok ? "intact" : "broken") : t("loading")}</span>
   <label className="flex items-center justify-between gap-3 text-sm">{t("language")} <select className="rounded-2xl border border-line bg-surface px-3 py-2" value={i18n.language} onChange={event => void i18n.changeLanguage(event.target.value)}><option value="fr">{t("fr")}</option><option value="en">{t("en")}</option></select></label>
   <div className="flex items-center justify-between gap-3">
    <span className={known ? paused ? "text-sm font-semibold text-bad" : "text-sm font-semibold text-ok" : "text-sm text-muted"}>{!known ? t("unknown") : t(paused ? "paused" : "running")}</span>
    <Button variant={paused ? "default" : "destructive"} disabled={!known || toggle.isPending} onClick={() => toggle.mutate(!!paused, { onError: () => toast.error(t("error")) })}>{paused ? <Play size={16}/> : <Pause size={16}/>}{t(paused ? "resume" : "pause")}</Button>
   </div>
  </Popover.Content></Popover.Portal>
 </Popover.Root>;
}
export default function App() {
 return <OperatorProvider><Shell/></OperatorProvider>;
}
function Shell() {
 const { t } = useTranslation();
 const { isAdmin } = useOperator();
 const navItems = pages.filter(([, path]) => isAdmin || !adminPages.has(path)).map(([ns, path]) => ({ to: path, end: path === "/", label: t(ns + ":title") }));
 return <BrowserRouter><div className="min-h-screen min-w-0 bg-canvas">
 <header className="mx-auto flex max-w-[1440px] flex-wrap items-center justify-between gap-x-5 gap-y-4 px-4 py-5 sm:px-6 lg:px-10">
  <Link to="/" className="text-lg font-bold tracking-tight text-ink">{t("product")}</Link>
  <div className="order-2 flex items-center gap-2 xl:order-3"><CommandPalette/><NotificationBell/><UserMenu/></div>
  <div className="order-3 w-full min-w-0 xl:order-2 xl:w-auto xl:flex-1"><PillNav items={navItems} label={t("navigation")}/></div>
 </header>
 <main className="mx-auto max-w-[1360px] min-w-0 px-6 pb-10 lg:px-10"><Suspense fallback={<p role="status">{t("loading")}</p>}><Routes>
 <Route path="/" element={<Home/>}/><Route path="/parc" element={<Parc/>}/><Route path="/cases" element={<CasesPage/>}/><Route path="/cases/:id" element={<CaseDetail/>}/>
 <Route path="/chat" element={<Chat/>}/><Route path="/documents" element={<Documents/>}/><Route path="/dashboard" element={<Dashboard/>}/><Route path="/purchase-guard" element={<PurchaseGuard/>}/>
 {isAdmin && <><Route path="/settings" element={<Settings/>}/><Route path="/demo" element={<Demo/>}/></>}<Route path="/journal" element={<Journal/>}/>
 <Route path="*" element={<h1>{t("notFound")}</h1>}/></Routes></Suspense></main><Toaster richColors/></div></BrowserRouter>;
}
