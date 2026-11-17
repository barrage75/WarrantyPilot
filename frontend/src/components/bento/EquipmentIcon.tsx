import type { ComponentProps } from "react";

import laptop from "@/assets/iso/laptop.webp";
import monitor from "@/assets/iso/monitor.webp";
import headphones from "@/assets/iso/headphones.webp";
import printer from "@/assets/iso/printer.webp";
import smartphone from "@/assets/iso/smartphone.webp";
import keyboard from "@/assets/iso/keyboard.webp";
import mouse from "@/assets/iso/mouse.webp";
import tablet from "@/assets/iso/tablet.webp";
import packageIcon from "@/assets/iso/package.webp";
import calendar from "@/assets/iso/calendar.webp";
import shield from "@/assets/iso/shield.webp";
import folder from "@/assets/iso/folder.webp";

const icons = { laptop, headphones, printer, monitor, smartphone, keyboard, mouse, tablet, package: packageIcon, calendar, shield, folder };
const categories: Record<string, keyof typeof icons> = {
 laptop: "laptop", computer: "laptop", notebook: "laptop", pc: "laptop", ordinateur: "laptop",
 headphones: "headphones", headphone: "headphones", headset: "headphones", casque: "headphones",
 printer: "printer", imprimante: "printer",
 monitor: "monitor", screen: "monitor", display: "monitor", ecran: "monitor", écran: "monitor",
 smartphone: "smartphone", phone: "smartphone", mobile: "smartphone", telephone: "smartphone", téléphone: "smartphone",
 keyboard: "keyboard", clavier: "keyboard", mouse: "mouse", souris: "mouse",
 tablet: "tablet", tablette: "tablet",
 calendar: "calendar", shield: "shield", folder: "folder",
};
export function EquipmentIcon({ category, size = 56, className, ...props }: Omit<ComponentProps<"img">, "src" | "alt" | "width" | "height"> & { category: string; size?: number }) {
 const key = categories[category.normalize("NFD").replace(/\p{Diacritic}/gu, "").toLowerCase()] ?? "package";
 return <img src={icons[key]} width={size} height={size} alt="" aria-hidden="true" data-icon={key} className={`shrink-0 object-contain ${className ?? ""}`} style={{ width: size, height: size }} {...props}/>;
}
