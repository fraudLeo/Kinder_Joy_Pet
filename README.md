# DeskPet 桌宠

Windows 桌面宠物。本项目的核心方向是 **Everything 功能扩展**：把本地文件秒级搜索能力接入桌宠，实现"搜文件 → 一键打开"的快捷体验，同时保留桌宠的常用功能。

## 🚀 Everything 功能扩展（核心方向）

本仓库用于开发桌宠与 [Everything](https://www.voidtools.com/)（Windows 本地文件秒搜工具）的集成扩展。

### 原理

Everything 平时把 NTFS 文件名维护成内存索引（读 MFT 建索引 + 监听 USN Journal 增量更新），搜索只是内存过滤。桌宠通过其命令行接口（`es.exe`）或 HTTP 服务器接口查询，即可获得毫秒级全盘文件搜索。

### 依赖

| 组件 | 状态 | 说明 |
|---|---|---|
| Everything | ✅ 已安装 | `D:\OtherSoftWare\search\Everything\Everything.exe`（1.4.1），需保持运行 |
| `es.exe`（命令行版） | ⏳ 待放置 | 官方下载：`https://www.voidtools.com/downloads/` → ES 命令行版，解压后放至 Everything 目录 |
| HTTP 服务器接口 | 🔀 备选 | Everything 选项 → HTTP 服务器（`allow_http_server=1` 已允许，需手动启用并重启） |

### 规划功能

- [ ] 桌宠右键菜单「搜文件」入口
- [ ] 关键字秒级搜索（调 `es.exe`，结果以完整路径返回）
- [ ] 结果列表窗口（非模态，双击/回车用默认程序打开）
- [ ] 与「快捷启动」联动（搜索即打开）
- [ ] 搜索历史与常用文件置顶

## 🐾 桌宠已有功能

- **卡比形象**：程序化绘制（粉色圆球、大眼跟随鼠标、眨眼动画）
- **消息气泡**：微信消息提醒演示（模拟源），果冻弹性上浮、跟随桌宠
- **Token 余量监控**：DeepSeek / OpenRouter / Kimi 多厂商余额 + 阈值预警
- **便利签**：左侧文件夹 + 右侧笔记，支持重命名、持久化
- **快捷启动**：右键菜单一键打开指定应用
- **实时日志**：非模态查看器，自动刷新，单实例

## 运行

```powershell
cd deskpet
pip install -r requirements.txt
python main.py
```

## 项目结构

```
deskpet/
├── main.py               # 入口：装配各模块
├── config.json           # 配置（含 everything_es_path 预留）
└── app/
    ├── pet.py            # 桌宠主窗口（卡比动画/拖拽/菜单/托盘）
    ├── bubbles.py        # 消息气泡
    ├── wechat_monitor.py # 消息源（DummySource / WcferrySource 骨架）
    ├── token_monitor.py  # 余额轮询 + 预警
    ├── providers/        # 余额厂商插件
    ├── launcher.py       # 快捷启动
    ├── sticky_note.py    # 便利签
    ├── settings.py       # 设置对话框
    └── logger.py         # 日志系统
```
