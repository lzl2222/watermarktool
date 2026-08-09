# 去水印 · Android 手机版（傻瓜教程）

> 手机本地运行的 豆包/小红书/抖音 无水印下载器。
> APK 由 GitHub 免费云端自动编译，你只需要推一次代码。

## 第一次：拿到 APK（约 10 分钟）

### 1. 创建 GitHub 仓库
1. 打开浏览器访问：**https://github.com/new**
2. 仓库名字随便填，例如 `watermarktool`（**不要勾选** README 初始化，保持空仓库）
3. 点绿色按钮创建

### 2. 把本项目推上去
在你电脑上打开 PowerShell，依次执行（把 `你的用户名` 换成你的 GitHub 用户名）：

```powershell
cd E:\WatermarkTool
git remote add origin https://github.com/你的用户名/watermarktool.git
git push -u origin master
```

> 第一次 push 会弹窗让你登录 GitHub（浏览器里登录一次即可）。

### 3. 等待自动编译
1. 打开仓库页面 → 点上方 **Actions** 标签
2. 会看到一个 `Build Android APK` 工作流在跑（约 5-10 分钟）
3. 跑完后点击该任务 → 底部 **Artifacts** → 下载 `watermarktool-apk`

### 4. 安装到小米手机
1. 把下载的 `.apk` 传到手机（微信/QQ 发文件或数据线）
2. 手机上点击 APK → 系统提示"未知来源"→ 允许 → 安装
3. 打开「去水印」，粘贴链接即可使用

## 以后更新版本
改完代码后：

```powershell
cd E:\WatermarkTool
git add -A
git commit -m "更新说明"
git push
```

Actions 会自动重新编译，去下载新的 APK 覆盖安装即可。

## 常见问题
| 问题 | 解决 |
|---|---|
| 安装提示"未知来源" | 设置 → 应用设置 → 特殊应用权限 → 安装未知应用 → 允许 |
| 下载的视频相册里看不到 | 稍等片刻或刷新相册；文件保存在「相册/去水印」目录 |
| 解析提示缺少凭证 | 链接必须从小红书 App 复制（含 xsec_token），重新复制完整分享文案 |
| 小米 HyperOS 限制 | App 是前台运行的，不受后台限制影响 |

## 技术信息
- 框架：Kivy 2.3（纯 Python，解析逻辑与桌面版完全复用）
- 架构：arm64-v8a（适配小米等主流安卓机）
- 保存：MediaStore 写入相册「去水印」目录（Android 10+，无需额外权限）
