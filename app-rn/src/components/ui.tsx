// components/ui.tsx — 液态玻璃组件（带动画）
import React, { useRef, useEffect } from "react";
import { Animated, Easing, Text, TouchableOpacity, View, ViewStyle } from "react-native";
import type { Theme } from "../theme";

// ── 玻璃按钮 ────────────────────────────────────────────────
export function GlassButton(props: {
  text: string; onPress?: () => void; theme: Theme;
  primary?: boolean; disabled?: boolean; height?: number; style?: ViewStyle; small?: boolean;
}) {
  const { text, onPress, theme, primary, disabled, height = 52, style, small } = props;
  const scale = useRef(new Animated.Value(1)).current;
  const bg = disabled ? (primary ? theme.accent + "88" : theme.glass) : primary ? theme.accent : theme.glass;
  const border = primary ? theme.accentDown : theme.glassBorder;
  const fg = primary ? "#FFFFFF" : theme.text;
  return (
    <TouchableOpacity
      activeOpacity={0.9}
      disabled={disabled}
      onPress={onPress}
      onPressIn={() => Animated.spring(scale, { toValue: 0.96, useNativeDriver: true, speed: 50 }).start()}
      onPressOut={() => Animated.spring(scale, { toValue: 1, useNativeDriver: true, speed: 50 }).start()}
      style={[{ transform: [{ scale }] }, style]}
    >
      <Animated.View style={{
        backgroundColor: bg, borderColor: border, borderWidth: 1,
        borderRadius: 16, height, alignItems: "center", justifyContent: "center",
        paddingHorizontal: small ? 12 : 16,
      }}>
        <Text style={{ color: fg, fontSize: small ? 13 : 16, fontWeight: "700" }}>{text}</Text>
      </Animated.View>
    </TouchableOpacity>
  );
}

// ── 旋转加载环 ──────────────────────────────────────────────
export function Spinner({ theme, size = 56 }: { theme: Theme; size?: number }) {
  const rot = useRef(new Animated.Value(0)).current;
  useEffect(() => {
    const anim = Animated.loop(Animated.timing(rot, { toValue: 1, duration: 800, easing: Easing.linear, useNativeDriver: true }));
    anim.start();
    return () => anim.stop();
  }, []);
  return (
    <View style={{ width: size, height: size, alignItems: "center", justifyContent: "center" }}>
      <Animated.View style={{
        width: size, height: size, borderRadius: size / 2,
        borderWidth: 3, borderColor: theme.glassBorder,
        borderTopColor: theme.accent,
        transform: [{ rotate: rot.interpolate({ inputRange: [0, 1], outputRange: ["0deg", "360deg"] }) }],
      }} />
    </View>
  );
}

// ── 进度胶囊 ────────────────────────────────────────────────
export function ProgressCapsule({ theme, progress, state, height = 54 }: {
  theme: Theme; progress: number; state: "idle" | "downloading" | "success" | "error"; height?: number;
}) {
  const color = state === "error" ? theme.err : state === "success" ? theme.ok : theme.accent;
  const label = state === "downloading" ? `${Math.round(progress * 100)}%`
    : state === "success" ? "已保存到相册" : state === "error" ? "下载失败" : "下载所选";
  return (
    <View style={{ height, borderRadius: 16, backgroundColor: color + "33", overflow: "hidden", alignItems: "center", justifyContent: "center" }}>
      <View style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: `${Math.max(progress * 100, progress > 0 ? 6 : 0)}%`, backgroundColor: color }} />
      <Text style={{ color: "#FFFFFF", fontWeight: "700", fontSize: 15, zIndex: 2 }}>{label}</Text>
    </View>
  );
}

// ── 胶囊徽章 ────────────────────────────────────────────────
export function Pill({ text, color }: { text: string; color: string }) {
  return (
    <View style={{ backgroundColor: color, borderRadius: 13, paddingHorizontal: 10, paddingVertical: 4, alignSelf: "flex-start" }}>
      <Text style={{ color: "#FFFFFF", fontSize: 12, fontWeight: "700" }}>{text}</Text>
    </View>
  );
}

// ── 卡片淡入 ────────────────────────────────────────────────
export function FadeIn({ children, style }: { children: React.ReactNode; style?: ViewStyle }) {
  const op = useRef(new Animated.Value(0)).current;
  const ty = useRef(new Animated.Value(8)).current;
  useEffect(() => {
    Animated.parallel([
      Animated.timing(op, { toValue: 1, duration: 250, useNativeDriver: true }),
      Animated.timing(ty, { toValue: 0, duration: 250, useNativeDriver: true }),
    ]).start();
  }, []);
  return <Animated.View style={[{ opacity: op, transform: [{ translateY: ty }] }, style]}>{children}</Animated.View>;
}
