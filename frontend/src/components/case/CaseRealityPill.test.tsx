import { afterEach, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import i18n from "@/i18n";
import { CaseRealityPill } from "./CaseRealityPill";

afterEach(cleanup);
it.each([
 ["fr", "real", "Réel"], ["fr", "reproduction", "Reproduction locale"], ["fr", "simulated", "Simulé"],
 ["en", "real", "Real"], ["en", "reproduction", "Local reproduction"], ["en", "simulated", "Simulated"],
] as const)("renders a sentence-case %s %s pill", async (language, value, label) => {
 await i18n.changeLanguage(language);
 render(<CaseRealityPill value={value}/>);
 expect(screen.getByText(label)).toHaveClass("rounded-full");
 expect(screen.queryByText(label.toLocaleUpperCase())).not.toBeInTheDocument();
});
