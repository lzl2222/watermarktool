// theme.ts — 液态玻璃主题（浅色/深色），配色遵循设计文档
export interface Theme {
  name: string;
  bg: string;
  grad: [string, string, string];
  headerText: string;
  headerSub: string;
  primary: string;
  accent: string;
  accentDown: string;
  panel: string;
  panelBorder: string;
  glass: string;      // 半透明面板
  glassBorder: string;
  text: string;
  textSec: string;
  textFaint: string;
  placeholder: string;
  ok: string;
  err: string;
  warn: string;
  card: string;
  cardBorder: string;
}

export const THEMES: Record<"glass_light" | "glass_dark", Theme> = {
  glass_dark: {
    name: "深色", bg: "#0F172A", grad: ["#1E3A8A", "#4C1D95", "#831843"],
    headerText: "#FFFFFF", headerSub: "#D3D9E6",
    primary: "#EC4899", accent: "#2563EB", accentDown: "#1D4ED8",
    panel: "#1B2536", panelBorder: "#33415A",
    glass: "rgba(255,255,255,0.08)", glassBorder: "rgba(255,255,255,0.16)",
    text: "#F1F5F9", textSec: "#A7B1C4", textFaint: "#6E7B91", placeholder: "#5A6780",
    ok: "#34D399", err: "#F87171", warn: "#FBBF24",
    card: "#1B2536", cardBorder: "#33415A",
  },
  glass_light: {
    name: "浅色", bg: "#F2F2F7", grad: ["#3B6CF5", "#7C5CF5", "#D25AAA"],
    headerText: "#0F172A", headerSub: "#334155",
    primary: "#7C3AED", accent: "#2563EB", accentDown: "#1D4ED8",
    panel: "#FFFFFF", panelBorder: "#E3E3EC",
    glass: "rgba(255,255,255,0.75)", glassBorder: "rgba(255,255,255,0.9)",
    text: "#1D1D1F", textSec: "#5B5B68", textFaint: "#8E8E9B", placeholder: "#B7B7C3",
    ok: "#16A34A", err: "#DC2626", warn: "#D97706",
    card: "#FFFFFF", cardBorder: "#E3E3EC",
  },
};
export const DEFAULT_THEME: keyof typeof THEMES = "glass_dark";
