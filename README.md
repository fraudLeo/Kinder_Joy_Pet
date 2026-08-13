# DeskPet 桌宠

Windows 桌宠：透明置顶动画宠物，集成**快捷启动应用、Token 余量监控预警、便利签、日志系统**。基于 PyQt6，实测内存占用约 45-50MB。

## 功能

- 🐾 **桌宠**：透明置顶窗口，支持 GIF 动画（无素材时内置眨眼占位动画），左键拖拽，右键菜单，系统托盘，关窗隐藏到托盘
- 🚀 **快捷启动**：右键菜单「快速启动」一键打开指定应用，设置面板管理
- 🔋 **Token 余量监控**：后台轮询多厂商余额（DeepSeek / OpenRouter / Kimi-Moonshot，插件式可扩展），低于阈值弹托盘预警（去重，恢复后重置）
- 📝 **便利签**：左侧文件夹列表 + 右侧笔记列表/文本框，支持新建/重命名/删除文件夹和笔记，编辑防抖自动保存，重启后恢复
- 💬 **消息气泡**：微信消息提醒（演示：右键菜单「模拟微信消息」开关触发假消息），气泡显示发送者+内容，多条消息果冻弹性上浮、最新在最底，超时淡出，跟随桌宠；接真实微信见 `app/wechat_monitor.py` 的 WcferrySource
- 📋 **日志系统**：滚动文件日志（`logs/deskpet.log`，2MB 轮转）+ 界面查看器

## 运行

```powershell
cd deskpet
pip install -r requirements.txt
python main.py
```

## 配置

所有配置存于 `config.json`（运行后也可在「设置」界面修改，自动写回）：

```jsonc
{
  "pet_size": 200,                // 桌宠尺寸
  "gif_path": "",                 // 本地 .gif 路径；留空用内置占位动画
  "token_check_interval_sec": 300,// 余额轮询间隔（秒）
  "token_warn_percent": 20,       // 余量低于该百分比时预警
  "providers": {                  // Token 厂商 API Key（设置界面填写）
    "deepseek": { "api_key": "" },
    "openrouter": { "api_key": "" },
    "moonshot": { "api_key": "" }
  },
  "launcher": {                   // 快捷启动应用
    "记事本": { "path": "notepad.exe", "args": "" }
  },
  "note_folders": {}              // 便利签数据（左侧文件夹 + 右侧笔记，自动管理）
}
```

## 扩展厂商

新增 `app/providers/xxx.py`，继承 `BalanceProvider` 并实现 `fetch()`，用 `@register` 注册即可，无需改动其他代码。

## 打包

```powershell
pip install pyinstaller
pyinstaller -F -w --name DeskPet main.py
```

## 项目结构

```
deskpet/
├── main.py               # 入口：装配各模块
├── config.json           # 配置
└── app/
    ├── pet.py            # 桌宠主窗口（动画/拖拽/菜单/托盘）
    ├── token_monitor.py  # 余额轮询 + 预警
    ├── providers/        # 余额厂商插件
    ├── launcher.py       # 快捷启动
    ├── sticky_note.py    # 便利签（文件夹 + 笔记）
    ├── bubbles.py        # 消息气泡（果冻上浮动画，跟随桌宠）
    ├── wechat_monitor.py # 消息源（DummySource 模拟 / WcferrySource 骨架）
    ├── settings.py       # 设置对话框
    └── logger.py         # 日志系统
```
