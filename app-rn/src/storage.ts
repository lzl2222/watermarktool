// storage.ts — 下载文件并保存到手机相册（expo-file-system 新 API + expo-media-library）
import * as FileSystem from "expo-file-system";

const EXT: Record<string, string> = {
  "image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "image/gif": ".gif",
  "video/mp4": ".mp4", "video/quicktime": ".mov",
};

export interface DlItem { url: string; fallback?: string; }

/** 轻量探测：读响应头拿 content-type 和状态（拿到头就中断 body） */
async function probe(url: string): Promise<{ ok: boolean; status: number; mime: string }> {
  const ctrl = new AbortController();
  try {
    const res = await fetch(url, { headers: { "User-Agent": "Mozilla/5.0" }, signal: ctrl.signal });
    const mime = (res.headers.get("content-type") || "").split(";")[0].trim().toLowerCase();
    const info = { ok: res.ok, status: res.status, mime };
    setTimeout(() => ctrl.abort(), 0);
    return info;
  } catch {
    return { ok: false, status: 0, mime: "" };
  }
}

/** 下载单个文件到本地缓存目录，返回 uri + mime + 修正后的文件名 */
export async function downloadItem(item: DlItem, name: string): Promise<{ uri: string; mime: string; fileName: string }> {
  let p = await probe(item.url);
  let src = item.url;
  if ((p.status === 403 || p.status === 404) && item.fallback) {
    p = await probe(item.fallback);
    src = item.fallback;
  }
  if (!p.ok) throw new Error(`下载失败 HTTP ${p.status || "?"}`);

  const ext = EXT[p.mime] || "";
  let fileName = name;
  if (ext && !fileName.toLowerCase().endsWith(ext)) fileName = fileName.replace(/\.[^.]*$/, "") + ext;

  const dir = new FileSystem.Directory(FileSystem.Paths.cache, "dl");
  await dir.create({ intermediates: true, idempotent: true });
  const dest = new FileSystem.File(dir, fileName);
  const file = await FileSystem.File.downloadFileAsync(src, dest, {
    headers: { "User-Agent": "Mozilla/5.0" },
    idempotent: true,
  });
  return { uri: file.uri, mime: p.mime, fileName };
}

/** 把本地文件保存到系统相册（授权后） */
export async function saveToGallery(localUri: string): Promise<string> {
  // 延迟导入：避免 Web 预览因原生模块加载崩溃（真机/Expo Go 正常）
  const MediaLibrary = await import("expo-media-library/legacy");
  const perm = await MediaLibrary.requestPermissionsAsync();
  if (!perm.granted) throw new Error("未获得相册权限，请在系统设置中允许");
  const asset = await MediaLibrary.createAssetAsync(localUri);
  return asset.uri;
}
