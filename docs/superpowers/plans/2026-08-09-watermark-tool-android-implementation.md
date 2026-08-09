# 去水印工具 · Android 手机版 实施计划

- 日期：2026-08-09
- 依据：docs/superpowers/specs/2026-08-09-watermark-tool-android-mobile-design.md（已获用户确认）

## 实施步骤（每步验证）

1. **mobile/core/**：复制 4 个解析器模块（platform_detector/doubao/xiaohongshu/douyin），确认纯 Python 可导入
2. **mobile/theme.py**：移动端主题（浅色/深色液态玻璃配色，与设计文档一致）
3. **mobile/icons.py**：PIL 绘制矢量图标（播放/暂停/下载/勾选/历史/主题/链接/图/动图/视频/删除）
4. **mobile/widgets.py**：玻璃组件库（玻璃按钮、进度胶囊、旋转加载环、玻璃卡片、胶囊徽章）+ 动画
5. **mobile/storage.py**：保存到 MediaStore（Android 9+）/公共下载目录（旧版），桌面端回退本地目录
6. **mobile/history.py**：SQLite 解析历史（50 条）
7. **mobile/main.py**：Kivy App（头部渐变玻璃条、输入框、解析流程、视频/图文结果渲染、下载进度、历史抽屉、主题切换）
8. **mobile/buildozer.spec** + **.github/workflows/build-android.yml**：GitHub Actions 自动编译 APK（arm64-v8a）
9. **mobile/README-安卓版.md**：傻瓜教程（建仓库链接 https://github.com/new → 推送 → 下载 APK → 小米安装）
10. **本机验证**：pip 安装 kivy，Windows 上运行同一套 UI 代码 + 真实解析器，截图核对每个界面/动画
11. **提交 Git + 交付教程**

## 验证清单
- [ ] core 导入无 tkinter/customtkinter 依赖
- [ ] 3 平台解析在 mobile 上下文跑通（联网）
- [ ] Windows 上 Kivy UI 启动、布局正确、动画正常（截图）
- [ ] 深/浅主题切换正常
- [ ] buildozer.spec 语法正确、Actions 工作流正确
