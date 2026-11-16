import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useReducedMotion } from "motion/react";

export function NumberTicker({ value, currency }: { value: number; currency?: "EUR" }) {
 const { i18n } = useTranslation();
 const reducedMotion = useReducedMotion();
 const animate = !reducedMotion && import.meta.env.MODE !== "test";
 const [display, setDisplay] = useState(animate ? 0 : value);
 useEffect(() => {
  if (!animate) { setDisplay(value); return; }
  const start = performance.now();
  let frame = 0;
  const tick = (now: number) => {
   const progress = Math.min((now - start) / 800, 1);
   setDisplay(value * (1 - (1 - progress) ** 3));
   if (progress < 1) frame = requestAnimationFrame(tick);
  };
  frame = requestAnimationFrame(tick);
  return () => cancelAnimationFrame(frame);
 }, [animate, value]);
 const format = (amount: number) => new Intl.NumberFormat(i18n.language, currency ? { style: "currency", currency, maximumFractionDigits: 0 } : { maximumFractionDigits: 0 }).format(amount);
 const finalValue = format(value);
 return <span aria-live="off" aria-label={finalValue}>{format(animate ? display : value)}</span>;
}
