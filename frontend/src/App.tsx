import { useCallback, useEffect, useState } from "react";
import en from "./i18n/en/l0.json";
import fr from "./i18n/fr/l0.json";
import type { components } from "./api/schema";
import "./style.css";

type CaseSummary = Pick<components["schemas"]["Case"], "id" | "status" | "badge">;

type Checks = {
  ok: boolean;
  checks: { name: string; ok: boolean; detail: string; fix_hint?: string }[];
};

type Translations = typeof fr;

function App() {
  const [language, setLanguage] = useState<"fr" | "en">("fr");
  const [cases, setCases] = useState<CaseSummary[]>([]);
  const [preflight, setPreflight] = useState<Checks | null>(null);
  const [journalOk, setJournalOk] = useState<boolean | null>(null);
  const [paused, setPaused] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const t: Translations = language === "fr" ? fr : en;

  const refresh = useCallback(async () => {
    try {
      const [casesResponse, preflightResponse, journalResponse, agentResponse] =
        await Promise.all([
          fetch("/api/cases"),
          fetch("/api/demo/preflight"),
          fetch("/api/journal/verify"),
          fetch("/api/agent/status"),
        ]);
      if (![casesResponse, preflightResponse, journalResponse, agentResponse].every((r) => r.ok)) {
        throw new Error("API request failed");
      }
      const [caseData, preflightData, journalData, agentData] = await Promise.all([
        casesResponse.json(),
        preflightResponse.json(),
        journalResponse.json(),
        agentResponse.json(),
      ]);
      setCases(caseData as CaseSummary[]);
      setPreflight(preflightData as Checks);
      setJournalOk(Boolean(journalData.ok));
      setPaused(Boolean(agentData.paused));
      setError(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function togglePause() {
    const response = await fetch(paused ? "/api/agent/resume" : "/api/agent/pause", {
      method: "POST",
    });
    if (!response.ok) {
      setError(t.actionFailed);
      return;
    }
    await refresh();
  }

  return (
    <main className="shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">WARRANTYPILOT · L0</p>
          <h1>{t.title}</h1>
        </div>
        <div className="controls">
          <button className="language" onClick={() => setLanguage(language === "fr" ? "en" : "fr")}>
            {language === "fr" ? "EN" : "FR"}
          </button>
          <button className={paused ? "button resume" : "button pause"} onClick={togglePause}>
            {paused ? t.resume : t.pause}
          </button>
        </div>
      </header>
      {error && <p className="error">{t.apiUnavailable}: {error}</p>}
      <section className="status-grid">
        <article className="panel">
          <div className="panel-heading">
            <h2>{t.journal}</h2>
            <span className={journalOk ? "pill good" : "pill bad"}>
              {journalOk === null ? t.loading : journalOk ? t.integrityOk : t.integrityFailed}
            </span>
          </div>
          <p>{t.journalDescription}</p>
        </article>
        <article className="panel">
          <div className="panel-heading">
            <h2>{t.preflight}</h2>
            <span className={preflight?.ok ? "pill good" : "pill bad"}>
              {preflight ? (preflight.ok ? t.ready : t.actionRequired) : t.loading}
            </span>
          </div>
          <ul className="check-list">
            {(preflight?.checks ?? []).map((check) => (
              <li key={check.name}>
                <span className={check.ok ? "check-mark" : "check-mark missing"}>
                  {check.ok ? "✓" : "!"}
                </span>
                <span>{check.detail}</span>
              </li>
            ))}
          </ul>
        </article>
      </section>
      <section className="panel cases-panel">
        <div className="panel-heading">
          <div>
            <p className="eyebrow">{t.workboard}</p>
            <h2>{t.cases}</h2>
          </div>
          <button className="button secondary" onClick={() => void refresh()}>{t.refresh}</button>
        </div>
        {cases.length === 0 ? (
          <p className="empty">{t.noCases}</p>
        ) : (
          <div className="case-list">
            {cases.map((item, index) => (
              <article className="case-row" key={item.id ?? `case-${index}`}>
                <code>{item.id?.slice(0, 8) ?? "—"}</code>
                <span>{t.statuses[item.status as keyof typeof t.statuses] ?? item.status}</span>
                <span className={`badge ${item.badge}`}>{t.badges[item.badge as keyof typeof t.badges] ?? item.badge}</span>
              </article>
            ))}
          </div>
        )}
      </section>
    </main>
  );
}

export default App;
