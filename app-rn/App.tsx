// App.tsx — 去水印（React Native / Expo）主界面
import React, { useRef, useState } from "react";
import {
  Alert, Animated, FlatList, Image, ScrollView, StatusBar,
  StyleSheet, Text, TextInput, TouchableOpacity, View, useWindowDimensions,
} from "react-native";
import { LinearGradient } from "expo-linear-gradient";
import { useVideoPlayer, VideoView } from "expo-video";
import { SafeAreaProvider, SafeAreaView } from "react-native-safe-area-context";
import AsyncStorage from "@react-native-async-storage/async-storage";

import { THEMES, DEFAULT_THEME, type Theme } from "./src/theme";
import { GlassButton, Spinner, ProgressCapsule, Pill, FadeIn } from "./src/components/ui";
import { extractUrl, detect, getMeta, type NoteMeta, type MediaItem } from "./src/core/platformDetector.ts";
import { parseXhs } from "./src/core/xhsParser.ts";
import { parseDoubao } from "./src/core/doubaoParser.ts";
import { parseDouyin } from "./src/core/douyinParser.ts";
import { downloadItem, saveToGallery } from "./src/storage";

type ViewState = "empty" | "loading" | "result" | "error";

const KEY_THEME = "wt_theme";

function AppInner() {
  const { width } = useWindowDimensions();
  const [themeName, setThemeName] = useState<keyof typeof THEMES>(DEFAULT_THEME);
  const theme: Theme = THEMES[themeName];

  const [urlText, setUrlText] = useState("");
  const [status, setStatus] = useState("支持 豆包 / 小红书 / 抖音，粘贴链接自动识别");
  const [statusColor, setStatusColor] = useState<string>(theme.textFaint);
  const [view, setView] = useState<ViewState>("empty");
  const [errorMsg, setErrorMsg] = useState("");
  const [meta, setMeta] = useState<NoteMeta | null>(null);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [parsing, setParsing] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [dlProgress, setDlProgress] = useState(0);
  const [dlState, setDlState] = useState<"idle" | "downloading" | "success" | "error">("idle");
  const parseRef = useRef(false);

  const platform = detect(urlText);
  const pm = getMeta(platform);
  const pad = 16;
  const cellW = (width - pad * 2 - 20) / 3;

  // ── 主题持久化 ────────────────────────────────────────────
  React.useEffect(() => { AsyncStorage.getItem(KEY_THEME).then(v => { if (v === "glass_light" || v === "glass_dark") setThemeName(v); }).catch(() => {}); }, []);
  const toggleTheme = () => {
    const n = themeName === "glass_dark" ? "glass_light" : "glass_dark";
    setThemeName(n);
    AsyncStorage.setItem(KEY_THEME, n).catch(() => {});
  };

  // ── 解析流程 ──────────────────────────────────────────────
  const doParse = async () => {
    if (parsing || downloading || parseRef.current) return;
    const text = urlText.trim();
    if (!text) { setStatus("请先粘贴分享链接"); setStatusColor(theme.warn); return; }
    const plat = detect(text);
    if (plat === "unknown") { setStatus("暂不支持该平台，目前支持：豆包/小红书/抖音"); setStatusColor(theme.warn); return; }
    parseRef.current = true; setParsing(true);
    setView("loading");
    setStatus(`正在解析 ${getMeta(plat).name} 链接…`); setStatusColor(theme.accent);
    try {
      const url = extractUrl(text);
      let m: NoteMeta;
      if (plat === "doubao") m = await parseDoubao(url);
      else if (plat === "xiaohongshu") m = await parseXhs(url);
      else m = await parseDouyin(url);
      setMeta(m);
      setSelected(new Set(m.media_items.map((_, i) => i)));
      setView("result");
      setStatus(`解析成功 | ${getMeta(m.platform).name} | 无水印`); setStatusColor(theme.ok);
    } catch (e: any) {
      setErrorMsg(e?.message || "解析失败");
      setView("error");
      setStatus("解析失败"); setStatusColor(theme.err);
    } finally {
      parseRef.current = false; setParsing(false);
    }
  };

  // ── 下载流程 ──────────────────────────────────────────────
  const doDownload = async () => {
    if (!meta || downloading) return;
    const items: MediaItem[] = meta.type === "video"
      ? meta.media_items
      : [...selected].sort((a, b) => a - b).map(i => meta.media_items[i]);
    if (!items.length) { setStatus("请先选择内容"); setStatusColor(theme.warn); return; }
    setDownloading(true); setDlState("downloading"); setDlProgress(0);
    const base = meta.note_id || "media";
    try {
      for (let i = 0; i < items.length; i++) {
        const it = items[i];
        const name = `${meta.platform}_${base}_${i + 1}${it.type === "live_photo" ? ".mp4" : ""}`;
        const { uri } = await downloadItem(it, name);
        await saveToGallery(uri);
        setDlProgress((i + 1) / items.length);
        setStatus(`已保存 ${name}`); setStatusColor(theme.ok);
      }
      setDlState("success");
      setStatus(`下载完成，共 ${items.length} 个文件已保存到相册`); setStatusColor(theme.ok);
    } catch (e: any) {
      setDlState("error");
      setStatus(`下载失败：${e?.message || ""}`); setStatusColor(theme.err);
    } finally {
      setDownloading(false);
      setTimeout(() => { setDlState("idle"); setDlProgress(0); }, 2500);
    }
  };

  // ── 内容渲染 ──────────────────────────────────────────────
  const renderContent = () => {
    if (view === "loading") {
      return (
        <FadeIn style={{ alignItems: "center", paddingTop: 60 }}>
          <Spinner theme={theme} />
          <Text style={[s.text, { color: theme.textSec, marginTop: 16, fontSize: 15 }]}>{status}</Text>
        </FadeIn>
      );
    }
    if (view === "error") {
      return (
        <FadeIn style={{ paddingTop: 40 }}>
          <Text style={{ color: theme.err, fontSize: 14, lineHeight: 22 }}>解析失败\n{errorMsg}</Text>
        </FadeIn>
      );
    }
    if (view === "result" && meta) {
      if (meta.type === "video") return renderVideo(meta);
      return renderGrid(meta);
    }
    return (
      <FadeIn style={{ alignItems: "center", paddingTop: 70 }}>
        <Text style={{ fontSize: 44, opacity: 0.4 }}>⬇</Text>
        <Text style={[s.text, { color: theme.textSec, fontSize: 17, fontWeight: "700", marginTop: 12 }]}>粘贴链接即可解析</Text>
        <Text style={[s.text, { color: theme.textFaint, fontSize: 13, marginTop: 6 }]}>支持 图文 / 动图 / 视频</Text>
      </FadeIn>
    );
  };

  // ── 视频结果 ──────────────────────────────────────────────
  const renderVideo = (m: NoteMeta) => <VideoResult meta={m} theme={theme} />;

  // ── 图文/动图网格 ─────────────────────────────────────────
  const toggleItem = (i: number) => {
    const next = new Set(selected);
    next.has(i) ? next.delete(i) : next.add(i);
    setSelected(next);
  };
  const renderGrid = (m: NoteMeta) => {
    const counts = { image: 0, live_photo: 0, video: 0 };
    m.media_items.forEach(it => { counts[it.type] = (counts[it.type] || 0) + 1; });
    const summary = `${counts.image ? `图 ${counts.image} ` : ""}${counts.live_photo ? `动图 ${counts.live_photo} ` : ""}${counts.video ? `视频 ${counts.video} ` : ""}共 ${m.media_items.length} 项`;
    const typeName = { image: "图", live_photo: "动图", video: "视频" };
    return (
      <FadeIn>
        <View style={{ flexDirection: "row", alignItems: "center", marginBottom: 8 }}>
          <Pill text={getMeta(m.platform).name} color={getMeta(m.platform).color} />
          <Text style={[s.text, { color: theme.textSec, fontSize: 13, marginLeft: 10 }]}>{summary}</Text>
        </View>
        <FlatList
          data={m.media_items}
          numColumns={3}
          keyExtractor={(_, i) => String(i)}
          scrollEnabled={false}
          columnWrapperStyle={{ gap: 10 }}
          contentContainerStyle={{ gap: 10 }}
          renderItem={({ item, index }) => {
            const sel = selected.has(index);
            return (
              <TouchableOpacity activeOpacity={0.85} onPress={() => toggleItem(index)}
                style={{ width: cellW, height: cellW, borderRadius: 14, overflow: "hidden",
                         backgroundColor: theme.card, borderWidth: 1, borderColor: theme.cardBorder }}>
                <Image source={{ uri: item.thumb || item.url }} style={{ width: cellW, height: cellW }} resizeMode="cover" />
                <View style={{ position: "absolute", left: 4, top: 4, borderRadius: 11, paddingHorizontal: 6, paddingVertical: 2, backgroundColor: item.type === "live_photo" ? theme.primary : "#64748B" }}>
                  <Text style={{ color: "#FFF", fontSize: 10, fontWeight: "700" }}>{typeName[item.type]}</Text>
                </View>
                <View style={{ position: "absolute", right: 6, bottom: 6, width: 22, height: 22, borderRadius: 11,
                               backgroundColor: sel ? theme.accent : "rgba(0,0,0,0.35)", alignItems: "center", justifyContent: "center" }}>
                  {sel && <Text style={{ color: "#FFF", fontSize: 13, fontWeight: "800" }}>✓</Text>}
                </View>
              </TouchableOpacity>
            );
          }}
        />
      </FadeIn>
    );
  };

  const selCount = meta ? [...selected].filter(i => i < (meta.media_items?.length || 0)).length : 0;
  const canDownload = meta && (meta.type === "video" || selCount > 0);
  const dlText = meta?.type === "video" ? "下载视频（无水印）" : canDownload ? `下载所选 (${selCount})` : "请选择要下载的内容";

  // ── 主布局 ────────────────────────────────────────────────
  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: theme.bg }}>
      <StatusBar barStyle={themeName === "glass_dark" ? "light-content" : "dark-content"} />
      <View style={{ flex: 1 }}>
        {/* 头部渐变玻璃条 */}
        <LinearGradient colors={theme.grad} start={{ x: 0, y: 0 }} end={{ x: 1, y: 0 }} style={{ paddingHorizontal: pad, paddingVertical: 14 }}>
          <View style={{ flexDirection: "row", alignItems: "center" }}>
            <View style={{ flex: 1 }}>
              <Text style={{ color: theme.headerText, fontSize: 20, fontWeight: "800" }}>去水印</Text>
              <Text style={{ color: theme.headerSub, fontSize: 11, marginTop: 2 }}>豆包 / 小红书 / 抖音 无水印一键下载</Text>
            </View>
            <GlassButton text={theme.name === "浅色" ? "深色" : "浅色"} small height={30} theme={theme} onPress={toggleTheme} />
          </View>
        </LinearGradient>

        {/* 输入区 */}
        <View style={{ paddingHorizontal: pad, paddingTop: 12 }}>
          <View style={{ borderRadius: 16, backgroundColor: theme.glass, borderWidth: 1, borderColor: theme.glassBorder, padding: 12 }}>
            <TextInput
              value={urlText}
              onChangeText={setUrlText}
              placeholder="粘贴 豆包/小红书/抖音 分享链接（支持整段文案）"
              placeholderTextColor={theme.placeholder}
              multiline
              style={{ color: theme.text, fontSize: 15, minHeight: 52, maxHeight: 100, textAlignVertical: "top" }}
            />
            <View style={{ flexDirection: "row", alignItems: "center", marginTop: 8 }}>
              {platform !== "unknown" && <Pill text={pm.name} color={pm.color} />}
              <View style={{ flex: 1 }} />
              <GlassButton text={parsing ? "解析中…" : "解析"} primary disabled={parsing} height={44} theme={theme} onPress={doParse} style={{ minWidth: 90 }} />
            </View>
          </View>
          <Text style={{ color: statusColor, fontSize: 12, marginTop: 8 }}>{status}</Text>
        </View>

        {/* 内容区 */}
        <ScrollView style={{ flex: 1 }} contentContainerStyle={{ paddingHorizontal: pad, paddingTop: 6, paddingBottom: 12 }}>
          {renderContent()}
        </ScrollView>

        {/* 底部下载 */}
        <View style={{ paddingHorizontal: pad, paddingBottom: 8, paddingTop: 4 }}>
          {dlState === "downloading" ? (
            <ProgressCapsule theme={theme} progress={dlProgress} state={dlState} />
          ) : (
            <GlassButton
              text={dlText}
              primary
              height={54}
              theme={theme}
              disabled={!canDownload || downloading}
              onPress={doDownload}
            />
          )}
        </View>
      </View>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({ text: {} });

export default function App() {
  return (
    <SafeAreaProvider>
      <AppInner />
    </SafeAreaProvider>
  );
}

// 视频结果组件（独立组件以便使用 useVideoPlayer hook）
function VideoResult({ meta, theme }: { meta: NoteMeta; theme: Theme }) {
  const item = meta.media_items[0];
  const player = useVideoPlayer(item.url, (p) => { p.loop = false; });
  const pm = getMeta(meta.platform);
  return (
    <FadeIn>
      <View style={{ flexDirection: "row", alignItems: "center", marginBottom: 10 }}>
        <Pill text={pm.name} color={pm.color} />
        <View style={{ width: 6 }} />
        <Pill text="无水印" color={theme.ok} />
      </View>
      <View style={{ alignItems: "center" }}>
        <VideoView player={player} style={{ width: 210, height: 374, borderRadius: 18 }} contentFit="contain" nativeControls />
      </View>
      <Text style={{ color: theme.textSec, fontSize: 13, marginTop: 10 }}>
        作者 {meta.author}{meta.width ? `  ${meta.width}x${meta.height}` : ""}
      </Text>
      {!!meta.text && <Text numberOfLines={2} style={{ color: theme.textSec, fontSize: 13, marginTop: 4 }}>{meta.text}</Text>}
    </FadeIn>
  );
}
