# 去水印工具 (Watermark Tool)

多平台无水印下载器（豆包 / 小红书 / 抖音），苹果液态玻璃主题桌面应用。

## 启动方式（无控制台窗口）

| 方式 | 说明 |
|---|---|
| 桌面快捷方式 `去水印工具.lnk` | 推荐，`pythonw.exe` 静默启动，无黑框 |
| 开始菜单快捷方式 | 同上 |
| `启动去水印工具.vbs` | 双击运行，无窗口 |
| `启动去水印工具.bat` | 兜底方案（会有短暂黑框） |

> 启动器都是直接运行源码（`pythonw app.py`），不打包成 exe，改代码后重启即生效，方便持续迭代。

## 依赖安装

```bash
pip install -r requirements.txt
```

## 项目结构

```
WatermarkTool/
├── app.py                  # 主程序（CustomTkinter GUI，液态玻璃主题）
├── theme.py                # 主题系统（浅色/深色液态玻璃）
├── platform_detector.py    # 平台识别 + 文本链接提取
├── doubao_parser.py        # 豆包视频解析（原画解密/匿名公开双通道）
├── xiaohongshu_parser.py   # 小红书解析（图文/动图/视频）
├── douyin_parser.py        # 抖音解析（公共API + share页兜底）
├── video_processor.py      # FFmpeg delogo 本地去水印（预留）
├── icon.ico                # 应用图标
├── requirements.txt        # 依赖清单
└── 启动*.vbs/.bat           # 无窗口启动器
```

## 使用提示

- 粘贴**整段分享文案**即可自动识别链接（小红书/抖音）
- 小红书链接必须包含 `xsec_token`（App 复制分享自带），否则会提示缺少凭证
- 顶部 `🌗` 按钮切换 浅色/深色 液态玻璃主题，选择持久化到 `config.json`

## 说明

- `config.json` 含 sessionid 等敏感信息，已加入 `.gitignore`
- 解析器均为纯逻辑模块（不依赖 GUI），便于后续移植为小程序/后端 API 复用
