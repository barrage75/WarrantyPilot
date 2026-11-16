import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useLocation } from "react-router-dom";
import i18n from "@/i18n";
import { renderWithApi, stubHttp } from "@/test/http";
import { EquipmentIcon } from "./EquipmentIcon";
import { NotificationBell } from "./NotificationBell";
import { NumberTicker } from "./NumberTicker";
import { PillNav } from "./PillNav";
import { StatusDot } from "./StatusDot";
import { WarrantyRing } from "./WarrantyRing";

beforeEach(async () => { await i18n.changeLanguage("fr"); });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

it("localizes the warranty ring label and maps its coverage color", () => {
 const { container, rerender } = render(<WarrantyRing daysLeft={119} coverage="expiring_soon"/>);
 expect(screen.getByRole("img", { name: "Garantie : 119 jours restants." })).toBeInTheDocument();
 expect(container.querySelector("[data-color=warn]")).toBeInTheDocument();
 rerender(<WarrantyRing daysLeft={null} coverage="leased"/>);
 expect(screen.getByText("loc.")).toBeInTheDocument();
 expect(container.querySelector("[data-color=idle]")).toBeInTheDocument();
 rerender(<WarrantyRing daysLeft={730} coverage="active"/>);
 expect(screen.getByText("2 ans")).toBeInTheDocument();
 expect(container.querySelector("[data-color=ok]")).toBeInTheDocument();
});

it("maps equipment categories to transparent illustration assets and falls back to a package", () => {
 const { container } = render(<><EquipmentIcon category="headset"/><EquipmentIcon category="screen"/><EquipmentIcon category="unknown-kind"/></>);
 const icons = Array.from(container.querySelectorAll("img"));
 expect(icons.map(icon => icon.getAttribute("src"))).toEqual(expect.arrayContaining([expect.stringContaining("headphones"), expect.stringContaining("monitor"), expect.stringContaining("package")]));
 expect(icons).toHaveLength(3);
 for (const icon of icons) {
  expect(icon).toHaveAttribute("alt", "");
  expect(icon).toHaveAttribute("aria-hidden", "true");
 }
});

function CurrentPath() { return <span data-testid="current-path">{useLocation().pathname}</span>; }
it("fetches notifications, counts urgent items and navigates to their case", async () => {
 stubHttp(call => call.path === "/api/notifications" ? Response.json([
  { id: "n1", kind: "case_awaiting_validation", severity: "critical", case_id: "case-1", equipment_id: null, due_at: null, params: {} },
  { id: "n2", kind: "warranty_expiring", severity: "warning", case_id: null, equipment_id: "eq-1", due_at: null, params: { equipment_label: "Dell", days_left: 4 } },
  { id: "n3", kind: "case_failed", severity: "info", case_id: null, equipment_id: null, due_at: null, params: {} },
 ]) : undefined);
 renderWithApi(<><NotificationBell/><CurrentPath/></>);
 await userEvent.click(screen.getByRole("button", { name: /Notifications/ }));
 expect(await screen.findByText("Urgent")).toBeInTheDocument();
 expect(screen.getByText("À traiter")).toBeInTheDocument();
 expect(screen.getByText("Dell : garantie à échéance dans 4 jours.")).toBeInTheDocument();
 await userEvent.click(screen.getByText("Un dossier attend votre validation."));
 expect(screen.getByTestId("current-path")).toHaveTextContent("/cases/case-1");
});

it("renders status and number components accessibly", () => {
 const { container } = render(<><StatusDot tone="active" label="Agent actif"/><NumberTicker value={1200} currency="EUR"/></>);
 expect(screen.getByRole("img", { name: "Agent actif" })).toBeInTheDocument();
 expect(container.querySelector(".animate-ping")).not.toBeNull();
 const ticker = container.querySelector('[aria-live="off"]');
 expect(ticker).toHaveAttribute("aria-label", new Intl.NumberFormat("fr", { style: "currency", currency: "EUR" }).format(1200));
 expect(ticker?.textContent?.replace(/\s+/g, " ")).toBe(new Intl.NumberFormat("fr", { style: "currency", currency: "EUR" }).format(1200).replace(/\s+/g, " "));
});

it("keeps every PillNav link keyboard-accessible when hiding the native scrollbar", async () => {
 const items = [{ to: "/", label: "Accueil", end: true }, { to: "/cases", label: "Dossiers" }, { to: "/chat", label: "Signalement" }];
 renderWithApi(<PillNav label="Navigation" items={items}/>);
 expect(screen.getByRole("navigation")).toHaveClass("overflow-x-auto", "[scrollbar-width:none]", "[&::-webkit-scrollbar]:hidden");
 for (const item of items) {
  const link = screen.getByRole("link", { name: item.label });
  link.scrollIntoView = vi.fn();
  await userEvent.tab();
  expect(link).toHaveFocus();
  expect(link).toHaveAttribute("href", item.to);
  expect(link.scrollIntoView).toHaveBeenCalledWith({ block: "nearest", inline: "nearest", behavior: "instant" });
 }
});
