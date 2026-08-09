// douyinParser.ts — 抖音视频解析器（TS 移植版）
import { extractUrl, type NoteMeta } from "./platformDetector.ts";

const UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36";

function removeWm(url: string): string {
  return url.replace(/playwm/g, "play").replace(/[?&]wm=[^&]*/g, "");
}

async function resolveVideoId(url: string): Promise<string> {
  const res = await fetch(url, { headers: { "User-Agent": UA }, redirect: "follow" });
  const final = res.url || url;
  for (const pat of [/\/video\/(\d+)/, /\/share\/video\/(\d+)/, /aweme_id=(\d+)/]) {
    const m = final.match(pat);
    if (m) return m[1];
  }
  for (const pat of [/\/video\/(\d+)/, /\/share\/video\/(\d+)/, /aweme_id=(\d+)/]) {
    const m = url.match(pat);
    if (m) return m[1];
  }
  return "";
}

async function parseViaPublicApi(shareUrl: string): Promise<NoteMeta> {
  const endpoints = [
    `https://api.douyin.wtf/api?url=${encodeURIComponent(shareUrl)}&minimal=false`,
    `https://api.douyin.wtf/api/hybrid/video_data?url=${encodeURIComponent(shareUrl)}`,
  ];
  for (const apiUrl of endpoints) {
    try {
      const res = await fetch(apiUrl, { headers: { "User-Agent": UA, Accept: "application/json", Referer: "https://www.douyin.com/" } });
      if (!res.ok) continue;
      const data = await res.json();
      if (![0, 200, "200"].includes(data?.code ?? data?.status_code ?? -1)) continue;
      let videoUrl = data?.video_url_no_watermark || data?.video_url || data?.url || "";
      if (!videoUrl) {
        const detail = data?.aweme_detail || data?.data || {};
        const addr = detail?.video?.play_addr || detail?.video?.download_addr || {};
        const urls = addr?.url_list || [];
        videoUrl = urls[0] || "";
      }
      if (!videoUrl) continue;
      const detail = data?.aweme_detail || data?.data || {};
      let cover = data?.cover || data?.origin_cover || "";
      if (!cover) {
        const cl = detail?.video?.cover?.url_list || [];
        cover = cl[0] || "";
      }
      const author = data?.author || data?.nickname || detail?.author?.nickname || "抖音用户";
      const desc = data?.desc || data?.title || "";
      videoUrl = removeWm(videoUrl);
      return {
        platform: "douyin", type: "video", note_id: String(data?.aweme_id || ""),
        title: desc, author: String(author), cover_url: cover,
        media_items: [{ type: "video", url: videoUrl, thumb: cover, index: 0 }],
        text: desc, no_watermark: true,
        width: Number(data?.video_width || 0), height: Number(data?.video_height || 0),
      };
    } catch { /* 下一个端点 */ }
  }
  throw new Error("抖音公共 API 解析失败");
}

async function parseViaSharePage(shareUrl: string): Promise<NoteMeta> {
  const videoId = await resolveVideoId(shareUrl);
  if (!videoId) throw new Error("无法从链接解析 video_id");
  const res = await fetch(`https://www.iesdouyin.com/share/video/${videoId}/`, {
    headers: { "User-Agent": UA, Referer: "https://www.douyin.com/" },
  });
  const html = await res.text();
  let videoUrl = "";
  for (const pat of [/<meta\s+property="og:video(?::url)?"\s+content="([^"]+)"/, /<meta\s+name="og:video"\s+content="([^"]+)"/, /"video_url"\s*:\s*"([^"]+)"/]) {
    const m = html.match(pat);
    if (m) { videoUrl = m[1]; break; }
  }
  if (!videoUrl) throw new Error("Share 页解析失败，页面未找到视频链接");
  const coverM = html.match(/<meta\s+property="og:image"\s+content="([^"]+)"/);
  const titleM = html.match(/<meta\s+property="og:title"\s+content="([^"]+)"/);
  videoUrl = removeWm(videoUrl);
  return {
    platform: "douyin", type: "video", note_id: videoId, title: titleM?.[1] || "",
    author: "抖音用户", cover_url: coverM?.[1] || "",
    media_items: [{ type: "video", url: videoUrl, thumb: coverM?.[1] || "", index: 0 }],
    text: titleM?.[1] || "", no_watermark: true,
  };
}

export async function parseDouyin(textOrUrl: string): Promise<NoteMeta> {
  const url = extractUrl(textOrUrl);
  try { return await parseViaPublicApi(url); } catch {}
  return parseViaSharePage(url);
}
