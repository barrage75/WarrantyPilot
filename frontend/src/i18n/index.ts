import i18n from "i18next";
import { initReactI18next } from "react-i18next";
const modules = import.meta.glob<{ default: Record<string, unknown> }>("./{fr,en}/*.json", { eager: true });
export const resources: Record<string, Record<string, Record<string, unknown>>> = { fr: {}, en: {} };
for (const [path, module] of Object.entries(modules)) {
 const [, language, namespace] = path.match(/\.\/(fr|en)\/(.+)\.json$/)!;
 resources[language][namespace] = module.default;
}
function savedLanguage() { try { return localStorage.getItem("wp-language") === "en" ? "en" : "fr"; } catch { return "fr"; } }
void i18n.use(initReactI18next).init({ resources, lng: savedLanguage(), fallbackLng: "fr", defaultNS: "common", interpolation: { escapeValue: false } });
function updateLanguage(language: string) {
 document.documentElement.lang = language;
 try { localStorage.setItem("wp-language", language); } catch { /* Storage may be unavailable. */ }
}
i18n.on("languageChanged", updateLanguage);
updateLanguage(i18n.language);
export default i18n;
