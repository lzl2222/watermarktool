// platformDetector.ts — 平台识别 + 文本链接提取（从 Python 版移植）
export type Platform = "doubao" | "xiaohongshu" | "douyin" | "unknown";

export function extractUrl(text: string): string {
  const src = (text || "").trim();
  const m = src.match(/https?:\/\/[^\s<>"']+/i);
  if (!m) return src;
  let url = m[0].replace(/[.,;:!?)\]}》】。，；：！？、…]+$/, "");
  while (url && ")]}>」』】】".includes(url[url.length - 1])) url = url.slice(0, -1);
  return url.trim();
}

export function detect(url: string): Platform {
  const u = (url || "").toLowerCase();
  if (u.includes("doubao.com") || u.includes("doubao.cn")) return "doubao";
  if (["xhslink.com", "xhslink.cn", "xiaohongshu.com", "xhs.cn", "xhscdn.com"].some(d => u.includes(d))) return "xiaohongshu";
  if (["v.douyin.com", "www.douyin.com", "iesdouyin.com", "douyin.com"].some(d => u.includes(d))) return "douyin";
  return "unknown";
}

export interface PlatformMeta { name: string; color: string; }
export const PLATFORM_META: Record<string, PlatformMeta> = {
  doubao: { name: "豆包", color: "#2563EB" },
  xiaohongshu: { name: "小红书", color: "#FF2442" },
  douyin: { name: "抖音", color: "#0B0B12" },
  unknown: { name: "未知", color: "#64748B" },
};
export function getMeta(p: Platform): PlatformMeta { return PLATFORM_META[p] || PLATFORM_META.unknown; }

export interface MediaItem { type: "image" | "live_photo" | "video"; url: string; fallback?: string; thumb?: string; index: number; }
export interface NoteMeta {
  platform: Platform; type: "image" | "live_photo" | "video";
  note_id: string; title: string; author: string; cover_url: string;
  media_items: MediaItem[]; text: string; no_watermark: boolean;
  width?: number; height?: number; _url?: string;
}
