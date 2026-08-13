# DeskPet 桌宠 —— 形象/模型修改分支

本分支用于**桌宠形象与模型修改**（卡比形象迭代）。

## 当前形象

- 🎈 卡比形象：粉色圆球身体、两只小手、大脚、竖长黑眼、小嘴
- 😌 眨眼动画：3 秒周期，每次眨眼 300ms
- 👀 眼球跟随：瞳孔朝鼠标方向偏移（最大 4px，30fps 刷新）
- 😮 张嘴互动：鼠标离桌宠越近嘴张得越大（60px 内最大、350px 外闭嘴，逐帧平滑过渡）

## 修改位置

| 内容 | 位置 |
|---|---|
| 形象绘制 | `app/pet.py` → `_draw_placeholder`（200px 基准坐标 + 等比缩放） |
| 眼球跟随 | `app/pet.py` → `_compute_eye_offset` / `_update_eye_follow` |
| 张嘴程度映射 | `app/pet.py` → `_mouth_target`（near=60 / far=350） |
| 眨眼状态机 | `app/pet.py` → `_tick_blink`（100ms 一拍，30 拍一周期） |

## 分支其他功能

- Everything 全局搜索（`app/everything.py`，右键菜单「搜文件」）
- Token 余量监控、便利签、消息气泡、快捷启动、实时日志
