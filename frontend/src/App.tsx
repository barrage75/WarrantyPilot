import { lazy, Suspense } from "react";
import { BrowserRouter, Link, Route, Routes } from "react-router-dom";
import { useTranslation } from "react-i18next";
import * as Popover from "@radix-ui/react-popover";
import { BarChart3, ChevronDown, FileText, FlaskConical, Folder, History, Home as HomeIcon, Laptop, MessageSquareWarning, Pause, Play, Settings as SettingsIcon, ShieldCheck } from "lucide-react";
import { Toaster, toast } from "sonner";
import { useAgentStatus, useToggleAgent, useJournal } from "@/api/hooks";
import { Button } from "@/components/ui/button";
import { NotificationBell, PillNav } from "@/components/bento";
import { CommandPalette } from "@/components/command/CommandPalette";
import laptopImage from "@/assets/iso/laptop.webp";
import horizontalLogo from "@/assets/brand/warranty-logo-horizontal.webp";
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
const pages = [
 ["home", "/", HomeIcon], ["parc", "/parc", Laptop], ["cases", "/cases", Folder],
 ["chat", "/chat", MessageSquareWarning], ["documents", "/documents", FileText],
 ["dashboard", "/dashboard", BarChart3], ["purchaseGuard", "/purchase-guard", ShieldCheck],
 ["settings", "/settings", SettingsIcon], ["demo", "/demo", FlaskConical], ["journal", "/journal", History],
] as const;
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
  <Popover.Trigger asChild><Button variant="outline" data-testid="user-menu-trigger" aria-label={tb("userMenu", { name: firstName })} className="gap-2 border-line px-2.5 text-ink">
   <span aria-hidden="true" className="grid h-7 w-7 place-items-center rounded-full bg-accent text-xs font-semibold text-white">{firstName.charAt(0).toLocaleUpperCase()}</span><span className="hidden sm:inline">{firstName}</span><ChevronDown size={16}/>
  </Button></Popover.Trigger>
  <Popover.Portal><Popover.Content align="end" sideOffset={10} className="z-50 w-[min(22rem,calc(100vw-2rem))] space-y-4 rounded-[20px] border border-line bg-surface p-5 text-ink shadow-[0_1px_2px_rgba(15,27,61,.04),0_6px_24px_rgba(37,99,235,.06)] outline-none">
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
 const navItems = pages.filter(([, path]) => isAdmin || !adminPages.has(path)).map(([ns, path, icon]) => ({ to: path, end: path === "/", icon, label: t(ns + ":title") }));
 return <BrowserRouter><div className="min-h-screen min-w-0 bg-canvas">
 <header className="relative z-30 flex flex-wrap items-center gap-x-3 gap-y-4 border-b border-line bg-surface px-4 py-3 sm:px-6 lg:fixed lg:inset-y-0 lg:left-0 lg:w-[264px] lg:flex-col lg:items-stretch lg:gap-8 lg:border-b-0 lg:border-r lg:px-6 lg:py-7">
  <Link to="/" className="flex min-w-0 flex-col items-start gap-1">
   <img src={horizontalLogo} alt={t("product")} className="h-7 w-auto"/>
   <span className="hidden max-w-[190px] text-xs leading-snug text-muted sm:block">{t("tagline")}</span>
  </Link>
  <div className="ml-auto flex shrink-0 items-center gap-2 lg:fixed lg:right-8 lg:top-4 lg:bg-surface">
   <CommandPalette/><NotificationBell/><UserMenu/>
  </div>
  <PillNav items={navItems} label={t("navigation")}/>
  <img src={laptopImage} alt="" aria-hidden="true" className="pointer-events-none absolute bottom-6 left-8 hidden h-28 w-48 object-contain lg:block"/>
 </header>
 <main className="mx-auto max-w-[1280px] min-w-0 px-4 pb-10 pt-6 sm:px-6 lg:ml-[264px] lg:px-10 lg:pt-24"><Suspense fallback={<p role="status">{t("loading")}</p>}><Routes>
 <Route path="/" element={<Home/>}/><Route path="/parc" element={<Parc/>}/><Route path="/cases" element={<CasesPage/>}/><Route path="/cases/:id" element={<CaseDetail/>}/>
 <Route path="/chat" element={<Chat/>}/><Route path="/documents" element={<Documents/>}/><Route path="/dashboard" element={<Dashboard/>}/><Route path="/purchase-guard" element={<PurchaseGuard/>}/>
 {isAdmin && <><Route path="/settings" element={<Settings/>}/><Route path="/demo" element={<Demo/>}/></>}<Route path="/journal" element={<Journal/>}/>
 <Route path="*" element={<h1>{t("notFound")}</h1>}/></Routes></Suspense></main><Toaster richColors/></div></BrowserRouter>;
}
