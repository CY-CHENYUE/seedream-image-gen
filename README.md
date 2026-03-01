# 🎨 Seedream Image Gen — OpenClaw 图片生成技能

使用字节跳动火山引擎 **Seedream API** 生成和编辑图片的 OpenClaw 技能。

## 功能特性

- **文生图** — 输入文字描述，生成高质量图片
- **图生图** — 基于已有图片进行编辑修改
- **多图角色融合** — 传入多张参考图，保持角色跨场景一致性
- **批量生成** — 一次生成 1-4 张变体
- **画面比例预设** — 内置 16:9、9:16、4:3 等常用比例，自动计算像素尺寸
- **多模型支持** — Seedream 4.0 / 4.5 / 5.0 / SeedEdit 3.0
- **最高 4K 分辨率**

## 安装

### 方式一：手动安装

将本仓库克隆到 OpenClaw 项目的 `skills/` 目录下：

```bash
cd 你的OpenClaw项目/skills/
git clone https://github.com/CY-CHENYUE/seedream-image-gen.git
```

### 方式二：ClawHub 安装

```bash
clawhub install seedream-image-gen
```

## 配置

### 1. 获取 API Key

前往 [火山引擎 Ark 控制台](https://console.volcengine.com/ark/region:ark+cn-beijing/apikey) 创建 API Key。

### 2. 配置 API Key

在 `openclaw.json` 中添加：

```json
{
  "skills": {
    "entries": {
      "seedream-image-gen": {
        "enabled": true,
        "apiKey": "你的ARK_API_KEY"
      }
    }
  }
}
```

或者直接设置环境变量：

```bash
export ARK_API_KEY="你的API_KEY"
```

## 使用示例

### 基础文生图

```bash
python3 scripts/generate_image.py --prompt "温馨的咖啡店内部，暖色灯光" --filename "咖啡店.png"
```

### 电影宽屏画面（16:9）

```bash
python3 scripts/generate_image.py \
  --prompt "远景，侦探走进昏暗的巷子，黑色电影风格" \
  --filename "frame01.png" \
  --aspect 16:9
```

### 角色设定图（高清方图）

```bash
python3 scripts/generate_image.py \
  --prompt "角色设定图，短发黑发年轻女性，白色衬衫，多角度" \
  --filename "角色_小美.png" \
  --aspect 1:1 --size 4K
```

### 图生图编辑

```bash
python3 scripts/generate_image.py \
  --prompt "把背景改成下雨的夜晚街道" \
  --filename "雨夜场景.png" \
  --input-image "./原图.png" \
  --model seededit-3.0
```

### 多图角色融合（保持角色一致性）

```bash
python3 scripts/generate_image.py \
  --prompt "同一个女孩坐在教室里，看着窗外" \
  --filename "frame05.png" \
  --ref-images "./角色_小美.png" \
  --aspect 16:9
```

### 批量生成

```bash
python3 scripts/generate_image.py \
  --prompt "神秘的森林小径，发光的蘑菇，奇幻风格" \
  --filename "森林.png" \
  --count 4
```

## 完整参数列表

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--prompt` / `-p` | 图片描述（必填） | - |
| `--filename` / `-f` | 输出文件名（必填） | - |
| `--model` / `-m` | 模型：`seedream-4.0` / `seedream-4.5` / `seedream-5.0` / `seedream-5.0-lite` / `seededit-3.0` | `seedream-4.5` |
| `--size` / `-s` | 分辨率：`1K` / `2K` / `4K` / `adaptive` / 精确像素 | `2K` |
| `--aspect` / `-a` | 画面比例：`16:9` / `9:16` / `4:3` / `3:4` / `1:1` / `3:2` / `2:3` | 无 |
| `--count` / `-c` | 生成数量（1-4） | `1` |
| `--input-image` / `-i` | 输入图片路径或 URL（图生图） | 无 |
| `--ref-images` / `-r` | 参考图片路径（角色融合，最多10张） | 无 |
| `--seed` | 随机种子 | 无 |
| `--guidance` | 引导系数（1.0-20.0） | 无 |
| `--no-watermark` | 关闭隐形水印 | 默认开启 |

## 画面比例预设

| 比例 | 适用场景 | 2K 像素 |
|------|----------|---------|
| `16:9` | 电影宽屏 / 分镜 | 2048x1152 |
| `9:16` | 竖屏短剧 / 手机端 | 1152x2048 |
| `4:3` | 经典电视 / PPT | 2048x1536 |
| `3:4` | 竖版海报 | 1536x2048 |
| `1:1` | 角色设定 / 头像 | 2048x2048 |
| `3:2` | 风景摄影 | 2048x1365 |
| `2:3` | 人像摄影 | 1365x2048 |

## 依赖

- **Python 3.7+**（无需额外第三方库，仅使用标准库）
- **火山引擎 Ark API Key**

## 技术说明

- **同步接口**：调用后直接返回结果，无需轮询
- **自动重试**：网络错误或限频时自动重试（最多 2 次）
- **SSL 安全**：优先使用系统证书验证，仅在沙箱环境验证失败时降级
- **本地图片支持**：自动将本地图片转换为 base64 data URL
- **MEDIA 输出**：生成后输出 `MEDIA: <路径>`，OpenClaw 可自动展示图片

## 外部接口说明

本技能会向以下地址发送请求：

| 接口 | 地址 | 发送的数据 |
|------|------|-----------|
| 火山引擎 Ark API | `https://ark.cn-beijing.volces.com/api/v3/images/generations` | prompt 文本、图片参数、API Key（认证头） |

除上述接口外，不会向任何其他地址发送数据。

## 许可证

MIT License
