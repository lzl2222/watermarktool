import { parseDouyin } from "./douyinParser.ts";

const text = `2.33 c@a.an ipq:/ 09/16 :4pm 【归墟】第十二集-归巢 本视频由小云雀Seedance2.5创作 这是一个由失踪案开始的逃亡、废土与新物种时代的原创长篇故事。从第一只巨蚁出现开始，城市失守，秩序崩塌，人类开始为活下去付出代价。 原创故事，长期连载中。# 小云雀创作者计划# 小云雀AI# 未来导演扶持计划# 抖音AI创作大赛 # 开放赛道  https://v.douyin.com/3b7oMxXsL4A/ 复制此链接，打开Dou音搜索，直接观看视频！`;
try {
  const r = await parseDouyin(text);
  console.log("成功 | 作者:", r.author, "| 标题:", (r.title||"").slice(0,40));
  console.log("url:", r.media_items[0].url.slice(0, 90));
} catch (e) {
  console.log("失败:", e.message.slice(0, 120));
}

// 诊断短链跳转
try {
  const UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36";
  const res = await fetch("https://v.douyin.com/3b7oMxXsL4A/", { headers: { "User-Agent": UA }, redirect: "follow" });
  console.log("短链跳转:", res.status, "->", res.url);
  const html = await res.text();
  const m = html.match(/\/video\/(\d+)/);
  console.log("video_id:", m ? m[1] : "未找到");
} catch (e) { console.log("跳转错误:", e.message.slice(0,80)); }
