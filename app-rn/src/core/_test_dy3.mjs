const UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1";
const UA2 = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36";
const vid = "7670057178891390214";

// 1) iesdouyin 分享页（桌面 UA）
let res = await fetch(`https://www.iesdouyin.com/share/video/${vid}/`, { headers: { "User-Agent": UA2, Referer: "https://www.douyin.com/" } });
let html = await res.text();
console.log("iesdouyin 桌面:", res.status, "len:", html.length, "| 有 play_addr:", html.includes("play_addr"), "| 有 url_list:", html.includes("url_list"), "| 有 _ROUTER_DATA:", html.includes("_ROUTER_DATA"), "| mp4:", /\.mp4/.test(html));

// 2) iesdouyin 分享页（移动 UA）
res = await fetch(`https://www.iesdouyin.com/share/video/${vid}/`, { headers: { "User-Agent": UA } });
html = await res.text();
console.log("iesdouyin 移动:", res.status, "len:", html.length, "| play_addr:", html.includes("play_addr"), "| url_list:", html.includes("url_list"), "| _ROUTER_DATA:", html.includes("_ROUTER_DATA"), "| mp4:", /\.mp4/.test(html));
