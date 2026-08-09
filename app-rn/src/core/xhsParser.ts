// xhsParser.ts — 小红书笔记解析器（TypeScript 移植版）
// 方案：短链/文本识别 → 带 xsec_token 请求页面 → 解析 __INITIAL_STATE__ → 原图/动图/视频
import { extractUrl, detect, type NoteMeta, type MediaItem, type Platform } from "./platformDetector.ts";

const UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36";
const ORIGIN_HOST = "https://sns-img-bd.xhscdn.com";

async function fetchText(url: string, headers: Record<string, string> = {}): Promise<string> {
  const res = await fetch(url, { headers: { "User-Agent": UA, "Accept-Language": "zh-CN,zh;q=0.9", ...headers }, redirect: "follow" });
  if (!res.ok) throw new Error(`请求失败 HTTP ${res.status}`);
  return res.text();
}

function parseQuery(url: string): Record<string, string> {
  const out: Record<string, string> = {};
  try { new URL(url).searchParams.forEach((v, k) => { out[k] = v; }); } catch {}
  return out;
}

function extractNoteId(url: string): string {
  const m = url.match(/\/(?:explore|discovery\/item|item)\/([a-f0-9]{24})/);
  return m ? m[1] : "";
}

async function resolveLink(url: string): Promise<{ noteId: string; token: string; finalUrl: string }> {
  let noteId = extractNoteId(url);
  let token = parseQuery(url)["xsec_token"] || "";
  if (noteId && token) return { noteId, token, finalUrl: url };
  // 短链跟随重定向
  const finalUrl = await fetchText(url, { "Accept-Language": "zh-CN,zh;q=0.9" }).then(() => "")
    .catch(() => "");
  // fetch 不暴露最终 URL，手动重定向：用 res.url
  const res = await fetch(url, { headers: { "User-Agent": UA, "Accept-Language": "zh-CN,zh;q=0.9" }, redirect: "follow" });
  const final = res.url || url;
  noteId = extractNoteId(final) || noteId;
  token = parseQuery(final)["xsec_token"] || token;
  return { noteId, token, finalUrl: final };
}

function cleanJsJson(raw: string): string {
  return raw
    .replace(/([,:]\s*)undefined(\s*[,\]}])/g, "$1null$2")
    .replace(/\[undefined\]/g, "[null]")
    .replace(/:!0([,\]}])/g, ":true$1")
    .replace(/:!1([,\]}])/g, ":false$1");
}

function extractInitState(html: string): any {
  const key = "__INITIAL_STATE__";
  const idx = html.indexOf(key);
  if (idx === -1) return null;
  let start = html.indexOf("=", idx) + 1;
  while (start < html.length && /\s/.test(html[start])) start++;
  const end = html.indexOf("</script>", start);
  if (end === -1) return null;
  let raw = html.slice(start, end).trim().replace(/;\s*$/, "");
  if (!raw) return null;
  try { return JSON.parse(cleanJsJson(raw)); } catch { return null; }
}

function imageToken(url: string): string {
  try {
    const parts = url.split("/");
    if (parts.length > 5) return parts.slice(5).join("/").split("!")[0];
  } catch {}
  const m = url.match(/\/([^/]+\/[^/]+)![^/]*$/);
  return m ? m[1] : "";
}
function originalImageUrl(url: string): string {
  const t = imageToken(url);
  return t && !t.includes("://") ? `${ORIGIN_HOST}/${t}` : url;
}

function bestImageUrl(img: any): string {
  const info = img?.infoList || [];
  for (const scene of ["WB_ORIGIN", "WB_HD", "WB_DFT"]) {
    for (const x of info) if (x?.imageScene === scene && x?.url) return x.url;
  }
  if (info.length) {
    const urls = info.map((x: any) => x?.url).filter(Boolean);
    if (urls.length) return urls[urls.length - 1];
  }
  return img?.urlDefault || img?.url || "";
}

function pickStreamUrl(stream: any): string {
  for (const codec of ["h264", "h265", "h266"]) {
    const arr = stream?.[codec] || [];
    for (const item of arr) {
      if (item?.masterUrl) return item.masterUrl;
      if (item?.backupUrls?.[0]) return item.backupUrls[0];
    }
  }
  return "";
}

function extractLiveVideo(img: any): string {
  const lp = img?.livePhoto;
  if (typeof lp === "string") return lp.trim();
  if (lp && typeof lp === "object") {
    const url = pickStreamUrl(lp?.video?.media?.stream);
    if (url) return url;
    for (const k of ["url", "videoUrl", "mainUrl"]) if (lp[k]) return lp[k];
  }
  return pickStreamUrl(img?.stream);
}

function bestVideoUrl(note: any): { url: string; backup: string; width: number; height: number; quality: string } {
  const stream = note?.video?.media?.stream || {};
  const rank: Record<string, number> = { "4k": 5, fhd: 4, hd: 3, sd: 2 };
  let best: any = null, bestRank = -1;
  for (const codec of ["h264", "h265", "h266"]) {
    for (const item of stream[codec] || []) {
      if (!item?.masterUrl && !item?.backupUrls) continue;
      const q = String(item?.qualityType || "").toLowerCase();
      const r = rank[q] || 1;
      if (r > bestRank) { bestRank = r; best = item; }
    }
  }
  if (!best) return { url: "", backup: "", width: 0, height: 0, quality: "" };
  return {
    url: best.masterUrl || "",
    backup: best.backupUrls?.[0] || "",
    width: Number(best.width) || 0,
    height: Number(best.height) || 0,
    quality: String(best.qualityType || ""),
  };
}

function parseInitState(state: any, noteId: string, sourceUrl: string): NoteMeta {
  const noteMap = state?.note?.noteDetailMap || {};
  let note: any = null;
  if (noteMap[noteId]) note = noteMap[noteId].note;
  else { const first = Object.values(noteMap)[0] as any; note = first?.note; }
  if (!note) throw new Error("页面中未找到笔记数据");

  const nid = note.noteId || noteId;
  const title = note.title || "";
  const desc = note.desc || "";
  const author = note?.user?.nickname || note?.user?.nickName || "小红书用户";
  const ntype = note.type || "normal";
  const imageList = note.imageList || [];

  if (ntype === "video") {
    const v = bestVideoUrl(note);
    if (!v.url) throw new Error("视频笔记中未找到视频播放地址");
    const cover = imageList.length ? bestImageUrl(imageList[0]) : "";
    return {
      platform: "xiaohongshu", type: "video", note_id: nid, title, author, cover_url: cover,
      media_items: [{ type: "video", url: v.url, fallback: v.backup, thumb: cover, index: 0 }],
      text: desc || title, no_watermark: true, width: v.width, height: v.height, _url: sourceUrl,
    };
  }

  const items: MediaItem[] = [];
  let hasLive = false;
  imageList.forEach((img: any, i: number) => {
    const display = bestImageUrl(img);
    const live = extractLiveVideo(img);
    if (live) {
      hasLive = true;
      items.push({ type: "live_photo", url: live, fallback: "", thumb: display, index: i });
    } else {
      items.push({ type: "image", url: originalImageUrl(display), fallback: display, thumb: display, index: i });
    }
  });
  if (!items.length) throw new Error("页面中未找到任何图片或视频内容");
  return {
    platform: "xiaohongshu", type: hasLive ? "live_photo" : "image", note_id: nid,
    title, author, cover_url: items[0].thumb || "", media_items: items,
    text: desc || title, no_watermark: true, _url: sourceUrl,
  };
}

export async function parseXhs(textOrUrl: string): Promise<NoteMeta> {
  const raw = (textOrUrl || "").trim();
  if (!raw) throw new Error("请输入小红书分享链接");
  const url = extractUrl(raw);
  if (!url.includes("xiaohongshu.com") && !url.includes("xhslink") && !url.includes("xhs.cn"))
    throw new Error("未识别到有效的小红书链接");

  const { noteId, token } = await resolveLink(url);
  if (!noteId) throw new Error("无法从链接中解析笔记 ID");
  if (!token) throw new Error("链接缺少访问凭证（xsec_token）。请重新从小红书 App 复制分享链接（含完整 xsec_token）。");

  const pageUrl = `https://www.xiaohongshu.com/explore/${noteId}?xsec_token=${encodeURIComponent(token)}&xsec_source=pc_feed`;
  const html = await fetchText(pageUrl, { Referer: "https://www.xiaohongshu.com/" });
  if (html.length < 1000) throw new Error("页面返回内容异常，可能被风控拦截，请稍后再试");

  const state = extractInitState(html);
  if (state) return parseInitState(state, noteId, url);
  throw new Error("页面解析失败，可能该笔记需要登录查看");
}
