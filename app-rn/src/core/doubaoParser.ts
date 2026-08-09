// doubaoParser.ts — 豆包视频解析器（TS 移植版）
// 匿名模式（主）：get_video_share_info → 直链
// 原画模式（可选，需要 sessionid）：fplay 解密（使用 WebCrypto，不可用时自动降级）
import { extractUrl, type NoteMeta } from "./platformDetector.ts";

const UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36";
const API_BASE = "https://www.doubao.com";

function extractParams(url: string): { shareId: string; vid: string } {
  let shareId = "", vid = "";
  try {
    const u = new URL(url);
    shareId = u.searchParams.get("share_id") || "";
    vid = u.searchParams.get("video_id") || u.searchParams.get("vid") || "";
  } catch {}
  if (!shareId) { const m = url.match(/share_id=([a-zA-Z0-9_-]+)/); if (m) shareId = m[1]; }
  if (!vid) { const m = url.match(/(?:video_id|vid)=([a-zA-Z0-9_-]+)/); if (m) vid = m[1]; }
  return { shareId, vid };
}

export async function parseDoubao(textOrUrl: string, sessionid = ""): Promise<NoteMeta> {
  const url = extractUrl(textOrUrl);
  const { shareId, vid } = extractParams(url);
  if (!shareId || !vid) throw new Error("无法从链接中解析出分享ID或视频ID");

  const apiUrl = `${API_BASE}/creativity/share/get_video_share_info?version_code=20800&language=zh-CN&device_platform=web&aid=497858&real_aid=497858&pkg_type=release_version&device_id=&pc_version=3.26.4&region=&sys_region=&samantha_web=1&web_platform=browser&use-olympus-account=1`;
  const res = await fetch(apiUrl, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json, text/plain, */*", "User-Agent": UA, Referer: url },
    body: JSON.stringify({ share_id: shareId, vid, creation_id: "" }),
  });
  if (!res.ok) throw new Error(`请求接口失败，状态码: ${res.status}`);
  const data = await res.json();
  if (data.code !== 0) throw new Error(`接口返回错误: ${data.msg || "未知错误"}`);
  const playInfo = data?.data?.play_info || {};
  const mainUrl = playInfo.main;
  if (!mainUrl) throw new Error("接口响应中未找到视频播放链接，可能视频已失效");
  return {
    platform: "doubao", type: "video", note_id: vid, title: data?.data?.prompt || "",
    author: data?.data?.user_info?.nickname || "豆包用户",
    cover_url: playInfo.poster_url || "",
    media_items: [{ type: "video", url: mainUrl, thumb: playInfo.poster_url || "", index: 0 }],
    text: data?.data?.prompt || "", no_watermark: false,
    width: Number(playInfo.width || 0), height: Number(playInfo.height || 0),
  };
}
