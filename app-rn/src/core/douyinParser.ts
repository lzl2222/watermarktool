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
  // 移动 UA：iesdouyin 分享页才会返回 _ROUTER_DATA 视频数据
  const UA_MOBILE = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1";
  const res = await fetch(`https://www.iesdouyin.com/share/video/${videoId}/`, {
    headers: { "User-Agent": UA_MOBILE, Referer: "https://www.douyin.com/" },
  });
  const html = await res.text();
  const m = html.match(/window\._ROUTER_DATA\s*=\s*(\{.*?\})\s*<\/script>/s);
  if (!m) throw new Error("分享页未包含视频数据");

  let data: any;
  try { data = JSON.parse(m[1]); }
  catch {
    data = JSON.parse(m[1].replace(/([,:]\s*)undefined(\s*[,\]}])/g, "$1null$2")
      .replace(/:!0([,\]}])/g, ":true$1").replace(/:!1([,\]}])/g, ":false$1"));
  }

  // 递归找 item（含 video.play_addr.url_list 与 desc 的对象）
  let item: any = null;
  (function walk(o: any): boolean {
    if (!o || typeof o !== "object") return false;
    if (o.video?.play_addr?.url_list?.length && typeof o.desc === "string") { item = o; return true; }
    for (const k of Object.keys(o)) { if (walk(o[k])) return true; }
    return false;
  })(data);

  if (!item) throw new Error("分享页数据中未找到视频信息");
  const list: string[] = item.video.play_addr.url_list || [];
  let videoUrl = list.find((u: string) => !u.includes("playwm")) || list[0] || "";
  if (!videoUrl) throw new Error("未找到视频播放地址");
  videoUrl = removeWm(videoUrl);
  const cover = item.video.cover?.url_list?.[0] || "";
  const author = item.author?.nickname || "抖音用户";
  return {
    platform: "douyin", type: "video", note_id: String(item.aweme_id || videoId),
    title: item.desc || "", author: String(author), cover_url: cover || "",
    media_items: [{ type: "video", url: videoUrl, thumb: cover || "", index: 0 }],
    text: item.desc || "", no_watermark: true,
  };
}

export async function parseDouyin(textOrUrl: string): Promise<NoteMeta> {
  const url = extractUrl(textOrUrl);
  try { return await parseViaPublicApi(url); } catch {}
  return parseViaSharePage(url);
}
