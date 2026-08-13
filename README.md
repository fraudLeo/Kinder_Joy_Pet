# DeskPet 桌宠 —— dev 集成分支

Windows 桌面宠物（PyQt6）：卡比形象、Everything 全局搜索、Token 余量监控、便利签、消息气泡、快捷启动、实时日志。

## 功能一览

- 🎈 **卡比形象**：粉球身体、小手、大脚、竖长黑眼、眨眼动画
- 👀 **互动**：眼球跟随鼠标、越近嘴张越大
- 🔍 **Everything 全局搜索**：右键菜单「搜文件」，秒级搜索 + 表格结果（名称/路径/大小/修改时间）+ 双击打开
- 🔋 **Token 余量**：DeepSeek / OpenRouter / Kimi 多厂商余额 + 阈值预警
- 📝 **便利签**：文件夹 + 笔记 + 重命名
- 💬 **消息气泡**：果冻动画，跟随桌宠（模拟源演示）
- 🚀 **快捷启动**、📋 **实时日志**、单实例锁

## 开发流程（Git Flow）

```
dev（集成分支，稳定可运行）
 │
 ├── 从 dev 拉最新
 │     git checkout dev && git pull
 │
 ├── 创建功能分支开发
 │     git checkout -b feature/xxx
 │
 ├── 功能分支上修改 + 测试
 │
 └── 测试无误后合并回 dev
       git checkout dev && git merge feature/xxx
```

### 约定

| 项 | 约定 |
|---|---|
| 集成分支 | `dev`（所有人从这里拉取） |
| 功能分支 | `feature/功能名`（如 `feature/search`、`feature/pet-appearance`） |
| 合并时机 | 功能分支自测通过后合并到 `dev`，不进 `master` |
| 协作方式 | 成员从 `dev` 拉取最新，在自己的功能分支上开发，互不干扰 |
| 本地配置 | `config.json` 已被 gitignore，分支切换不会影响本地密钥/路径配置 |

## 形象修改位置

| 内容 | 位置 |
|---|---|
| 形象绘制 | `app/pet.py` → `_draw_placeholder`（200px 基准坐标 + 缩放） |
| 眼球跟随 | `app/pet.py` → `_compute_eye_offset` / `_update_eye_follow` |
| 张嘴程度 | `app/pet.py` → `_mouth_target`（near=60 / far=350） |
| 眨眼状态机 | `app/pet.py` → `_tick_blink`（100ms 一拍，30 拍一周期） |

## 运行

```powershell
pip install -r requirements.txt
python main.py
```

依赖：PyQt6、requests；Everything 搜索需 Everything 运行 + `lib/es.exe`。
