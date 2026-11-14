import { Headphones, Keyboard, Laptop, Monitor, Mouse, Package, Printer, Smartphone, Tablet } from "lucide-react";
import type { ComponentProps } from "react";

const icons = { laptop: Laptop, headphones: Headphones, printer: Printer, monitor: Monitor, smartphone: Smartphone, keyboard: Keyboard, mouse: Mouse, tablet: Tablet, package: Package };
const categories: Record<string, keyof typeof icons> = {
 laptop: "laptop", computer: "laptop", notebook: "laptop", pc: "laptop", ordinateur: "laptop",
 headphones: "headphones", headphone: "headphones", headset: "headphones", casque: "headphones",
 printer: "printer", imprimante: "printer",
 monitor: "monitor", screen: "monitor", display: "monitor", ecran: "monitor", écran: "monitor",
 smartphone: "smartphone", phone: "smartphone", mobile: "smartphone", telephone: "smartphone", téléphone: "smartphone",
 keyboard: "keyboard", clavier: "keyboard", mouse: "mouse", souris: "mouse",
 tablet: "tablet", tablette: "tablet",
};
export function EquipmentIcon({ category, size = 56, ...props }: Omit<ComponentProps<"svg">, "children"> & { category: string; size?: number }) {
 const key = categories[category.normalize("NFD").replace(/\p{Diacritic}/gu, "").toLowerCase()] ?? "package";
 const Icon = icons[key];
 return <Icon aria-hidden="true" data-icon={key} size={size} strokeWidth={1.75} {...props}/>;
}
