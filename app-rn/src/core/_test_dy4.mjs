const UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1";
const vid = "7670057178891390214";
const res = await fetch(`https://www.iesdouyin.com/share/video/${vid}/`, { headers: { "User-Agent": UA } });
const html = await res.text();
const m = html.match(/window\._ROUTER_DATA\s*=\s*(\{.*?\})\s*<\/script>/s);
if (!m) { console.log("未匹配 _ROUTER_DATA"); }
else {
  // 尝试 JSON.parse（可能有 JS 字面量）
  let data;
  try { data = JSON.parse(m[1]); }
  catch { data = JSON.parse(m[1].replace(/([,:]\s*)undefined(\s*[,\]}])/g, "$1null$2").replace(/:!0([,\]}])/g, ":true$1").replace(/:!1([,\]}])/g, ":false$1")); }
  const loaderData = data?.loaderData;
  // 找 video 字段
  function findVideo(obj, path) {
    if (!obj || typeof obj !== "object") return null;
    if (obj.play_addr && obj.play_addr.url_list) return { url: obj.play_addr.url_list[0], path };
    for (const k of Object.keys(obj)) {
      const r = findVideo(obj[k], path + "." + k);
      if (r) return r;
    }
    return null;
  }
  const v = findVideo(data, "data");
  if (v) console.log("视频URL:", v.url.slice(0, 120), "\n路径:", v.path);
  else console.log("未找到 play_addr.url_list");
  // 也找标题/作者
  const desc = JSON.stringify(data).match(/"desc":"([^"]{0,60})/);
  if (desc) console.log("desc:", desc[1]);
}
