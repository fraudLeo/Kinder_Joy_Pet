# DeskPet 桌宠 —— 网页搜索功能

本分支（f4）负责**网页搜索功能**：输入关键字拼入搜索引擎 URL 打开浏览器，以及拖放链接到桌宠直接跳转网页。

## 功能

### 1. 关键字网页搜索

右键桌宠 → 「网页搜索」→ 输入关键字 → 选择引擎 → 回车（或点击搜索）→ 系统默认浏览器（Edge/Chrome）打开搜索结果页。

- 三引擎可切换：**百度**、**Google**、**Bing**
- 关键字经 URL 编码（`quote_plus`），中文/特殊字符不会乱码
- 搜索窗口为非模态单实例，粉色系风格，不遮挡桌宠操作

### 2. 拖放 URL 直接跳转

把网页链接拖到桌宠（卡比）身上松手 → 自动用默认浏览器打开该网页。

- 支持从浏览器地址栏拖出的链接（`text/uri-list`）
- 支持聊天软件/文档中的链接文本（自动从文本中提取 `http(s)://` 开头的 URL）
- 安全边界：只接受 `http://` / `https://`，`file://` 等本地协议一律忽略

## 实现位置

| 内容 | 位置 |
|---|---|
| 引擎 URL 模板 | `app/web_search.py` → `SEARCH_ENGINES`（新增引擎加一行模板即可） |
| URL 拼接 | `app/web_search.py` → `build_url`（`{kw}` 占位 + `quote_plus` 编码） |
| 搜索/打开链接 | `app/web_search.py` → `open_search` / `open_url`（`webbrowser.open`） |
| 搜索窗口 | `app/web_search.py` → `WebSearchDialog`（输入框 + 引擎下拉 + 搜索按钮） |
| 拖放事件 | `app/pet.py` → `dragEnterEvent` / `dropEvent` / `_extract_url`（MIME 解析） |
| 菜单与入口 | `app/pet.py` 菜单「网页搜索」；`main.py` → `open_web_search` / `open_web_url` |

## 技术要点

```
关键字 ──quote_plus──► URL 模板 ──► webbrowser.open ──► 默认浏览器
拖放链接 ──MIME 解析──► http(s) 校验 ──► 同上
```

- 拖放解析：优先 `mimeData.hasUrls()`，回退到文本正则提取 `https?://\S+`
- 新增搜索引擎：在 `SEARCH_ENGINES` 表加一行，如
  `"搜狗": "https://www.sogou.com/web?query={kw}"`
