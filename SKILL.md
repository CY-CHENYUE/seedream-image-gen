---
name: seedream-image-gen
description: 使用字节跳动 Seedream API 生成和编辑图片。支持文生图、图生图编辑、多图角色融合、批量生成。
version: 1.0.0
tools: Bash, Read
metadata: {"clawdbot":{"emoji":"🎨","primaryEnv":"ARK_API_KEY","homepage":"https://github.com/CY-CHENYUE/seedream-image-gen","requires":{"bins":["python3"],"env":["ARK_API_KEY"]}}}
---

# Seedream 图片生成

使用字节跳动火山引擎 Seedream API 生成图片（同步接口，无需轮询）。

## 首次使用配置（最高优先级）

**每次执行技能前，必须先检查环境变量。**

### 检查步骤

```bash
echo "ARK_API_KEY=${ARK_API_KEY:-(未设置)}"
```

- 已存在 → 跳过本节，直接执行用户请求
- 显示「未设置」→ 执行下方配置步骤

### 补全缺失的 ARK_API_KEY

**向用户索取 API Key：**
> 需要配置火山引擎 API Key 才能生成图片。请提供：
> - **ARK_API_KEY** — 在 [火山引擎 Ark 控制台](https://console.volcengine.com/ark/region:ark+cn-beijing/apikey) 中创建并复制

**用户提供后，写入专用配置文件（幂等）：**

```bash
# 创建或更新 ~/.seedream.env（专用配置文件，避免污染 ~/.zshrc）
touch ~/.seedream.env && chmod 600 ~/.seedream.env
# 幂等写入：已存在则替换，不存在则追加
grep -q '^export ARK_API_KEY=' ~/.seedream.env \
  && sed -i '' 's|^export ARK_API_KEY=.*|export ARK_API_KEY="用户提供的Key"|' ~/.seedream.env \
  || echo 'export ARK_API_KEY="用户提供的Key"' >> ~/.seedream.env
# 确保 ~/.zshrc 会加载此文件（幂等，只加一次）
grep -q 'source ~/.seedream.env' ~/.zshrc || echo '[ -f ~/.seedream.env ] && source ~/.seedream.env' >> ~/.zshrc
# 当前会话立即生效
source ~/.seedream.env
```

> **安全提醒**：写入完成后，**不要在聊天中回显 API Key 明文**。只需告诉用户「API Key 已保存」。

### 配置完成

告诉用户：
> API Key 已保存到 `~/.seedream.env`，后续使用无需再次配置。

然后**继续执行用户原本的请求**，执行命令前先 `source ~/.seedream.env` 确保变量可用：

```bash
source ~/.seedream.env && python3 {baseDir}/scripts/generate_image.py --prompt "xxx" --filename "xxx.png"
```

## 快速开始

```bash
python3 {baseDir}/scripts/generate_image.py --prompt "穿红裙的女孩站在海边，电影感光影" --filename "scene01.png"
```

## 完整参数

```bash
python3 {baseDir}/scripts/generate_image.py \
  --prompt "图片描述" \
  --filename "output.png" \
  --model seedream-5.0 \
  --size 2K \
  --aspect 16:9 \
  --count 1 \
  --input-image "参考图.png" \
  --ref-images "角色1.png" "角色2.png" \
  --seed 42 \
  --guidance 7.5 \
  --no-watermark
```

## 参数说明

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--prompt` | 图片描述（必填） | - |
| `--filename` | 输出文件名（必填） | - |
| `--model` | 模型选择：`seedream-4.0`、`seedream-4.5`、`seedream-5.0`、`seedream-5.0-lite`、`seededit-3.0` | `seedream-5.0` |
| `--size` | 分辨率：`1K`、`2K`、`4K`、`adaptive`，或精确像素如 `1920x1080` | `2K` |
| `--aspect` | 画面比例快捷设置：`16:9`、`9:16`、`4:3`、`3:4`、`1:1`、`3:2`、`2:3` | 无（使用 --size） |
| `--count` | 生成数量（1-4 张） | `1` |
| `--input-image` | 输入图片的 URL 或本地路径，用于图生图编辑 | 无 |
| `--ref-images` | 多张参考图路径，用于角色融合保持一致性（最多 10 张） | 无 |
| `--seed` | 随机种子，用于复现相同结果 | 无 |
| `--guidance` | 引导系数 1.0-20.0（越高越贴合提示词） | 无 |
| `--no-watermark` | 关闭隐形水印 | 默认开启水印 |

## 画面比例预设（--aspect）

使用 `--aspect` 时，脚本会自动计算最佳像素尺寸：

| 比例 | 适用场景 | 2K 像素 |
|------|----------|---------|
| `16:9` | 电影宽屏 / 分镜画面 | 2048x1152 |
| `9:16` | 竖屏短剧 / 手机端 | 1152x2048 |
| `4:3` | 经典电视 / 演示文稿 | 2048x1536 |
| `3:4` | 竖版海报 / 人像 | 1536x2048 |
| `1:1` | 角色设定图 / 头像 | 2048x2048 |
| `3:2` | 风景摄影 | 2048x1365 |
| `2:3` | 人像摄影 | 1365x2048 |

## 使用示例

### 1. 基础文生图
```bash
python3 {baseDir}/scripts/generate_image.py --prompt "温馨的咖啡店内部，暖色灯光，水彩画风格" --filename "咖啡店.png"
```

### 2. 电影宽屏画面
```bash
python3 {baseDir}/scripts/generate_image.py --prompt "远景，侦探走进昏暗的巷子，黑色电影风格，戏剧性阴影" --filename "frame01.png" --aspect 16:9
```

### 3. 角色设定图
```bash
python3 {baseDir}/scripts/generate_image.py --prompt "角色设定图，短发黑发年轻女性，白色衬衫，多角度，正面和侧面" --filename "角色_小美.png" --aspect 1:1 --size 4K
```

### 4. 图生图编辑（更换场景）
```bash
python3 {baseDir}/scripts/generate_image.py --prompt "把背景改成下雨的夜晚街道" --filename "雨夜场景.png" --input-image "./原始场景.png" --model seededit-3.0
```

### 5. 多图角色融合（跨场景保持角色一致性）
```bash
python3 {baseDir}/scripts/generate_image.py --prompt "同一个女孩坐在教室里，看着窗外，柔和的午后阳光" --filename "frame05.png" --ref-images "./角色_小美.png" --aspect 16:9
```

### 6. 批量生成（多个变体）
```bash
python3 {baseDir}/scripts/generate_image.py --prompt "神秘的森林小径，发光的蘑菇，奇幻风格" --filename "森林.png" --count 4
```

## 生成结果反馈

图片生成成功后，脚本会输出详细信息。**你必须将以下关键信息反馈给用户：**

1. **使用的模型**：模型别名和实际模型 ID（如 `seedream-5.0（doubao-seedream-5-0-260128）`）
2. **实际像素尺寸**：下载图片的真实分辨率（如 `2048x1152`）
3. **文件大小**：图片文件的实际大小（如 `1.23 MB`）
4. **生成耗时**：从请求到完成的时间
5. **画面比例**：如果使用了 `--aspect` 参数，说明使用的比例（如 `16:9`）

示例反馈格式：

```
图片已生成完成：
- 模型：seedream-5.0（doubao-seedream-5-0-260128）
- 尺寸：2048x1152（16:9）
- 文件大小：1.23 MB
- 耗时：5.2 秒
```

## 注意事项

- 同步接口：生成完成后直接返回结果，无需轮询
- 下载的图片是 API 返回的原图，未经任何压缩或缩放
- 生成的图片 URL 有效期为 24 小时
- 脚本输出 `MEDIA: <路径>` 用于在对话中自动展示图片
- 建议文件名中包含时间戳或场景编号，方便管理
- 批量生成时，文件自动命名为 `输出名_001.png`、`输出名_002.png` 等
- 多图融合（--ref-images）在 Seedream 4.0 和 4.5 上效果最好
