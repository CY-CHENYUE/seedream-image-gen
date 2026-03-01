#!/usr/bin/env python3
"""
Seedream 图片生成脚本
使用字节跳动火山引擎 Seedream API 生成图片。

功能：
  - 文生图（文字描述 → 图片）
  - 图生图（基于已有图片编辑）
  - 多图角色融合（传入多张参考图保持角色一致性）
  - 批量生成（一次生成多张变体）
  - 画面比例预设（16:9 / 9:16 等）

用法：
    python3 generate_image.py --prompt "描述" --filename "输出.png"
    python3 generate_image.py --prompt "描述" --filename "输出.png" --aspect 16:9 --model seedream-4.5
    python3 generate_image.py --prompt "编辑指令" --filename "编辑后.png" --input-image "原图.png"
    python3 generate_image.py --prompt "同一角色新场景" --filename "分镜.png" --ref-images "角色.png"
"""

import argparse
import base64
import json
import os
import ssl
import struct
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional, Tuple

# ============================================================
# 配置
# ============================================================

API_BASE = "https://ark.cn-beijing.volces.com/api/v3/images/generations"

MODEL_MAP = {
    "seedream-4.0": "doubao-seedream-4-0-250828",
    "seedream-4.5": "doubao-seedream-4-5-251128",
    "seedream-5.0": "doubao-seedream-5-0-260128",
    "seedream-5.0-lite": "doubao-seedream-5-0-lite-260128",
    "seededit-3.0": "doubao-seededit-3-0-i2i-250628",
}

# 画面比例预设 -> (宽, 高)，基于 2K 分辨率
ASPECT_RATIOS = {
    "16:9": (2048, 1152),
    "9:16": (1152, 2048),
    "4:3": (2048, 1536),
    "3:4": (1536, 2048),
    "1:1": (2048, 2048),
    "3:2": (2048, 1365),
    "2:3": (1365, 2048),
}

MAX_RETRIES = 2       # 最大重试次数
RETRY_DELAY = 3       # 重试间隔（秒）


# ============================================================
# 工具函数
# ============================================================

def get_api_key() -> str:
    """从环境变量获取 API Key。"""
    key = os.environ.get("ARK_API_KEY") or os.environ.get("SEEDREAM_API_KEY")
    if not key:
        print("错误：未设置 ARK_API_KEY 环境变量。", file=sys.stderr)
        print("", file=sys.stderr)
        print("配置方法：", file=sys.stderr)
        print("  1. 获取 API Key：https://console.volcengine.com/ark/region:ark+cn-beijing/apikey", file=sys.stderr)
        print("  2. 在 openclaw.json 中配置：", file=sys.stderr)
        print('     { "skills": { "entries": { "seedream-image-gen": { "apiKey": "你的KEY" } } } }', file=sys.stderr)
        sys.exit(1)
    return key


def resolve_size(size: Optional[str], aspect: Optional[str]) -> Optional[str]:
    """根据 --size 和 --aspect 参数计算最终图片尺寸。"""
    if aspect:
        if aspect not in ASPECT_RATIOS:
            print(f"错误：不支持的画面比例 '{aspect}'。", file=sys.stderr)
            print(f"支持的比例：{', '.join(ASPECT_RATIOS.keys())}", file=sys.stderr)
            sys.exit(1)
        w, h = ASPECT_RATIOS[aspect]
        # 根据分辨率预设缩放
        if size == "4K":
            w, h = w * 2, h * 2
        elif size == "1K":
            w, h = w // 2, h // 2
        return f"{w}x{h}"
    return size


def image_to_url(image_path: str) -> str:
    """将本地图片路径转为 data URL，如果已经是 URL 则直接返回。"""
    if image_path.startswith("http://") or image_path.startswith("https://"):
        return image_path

    path = Path(image_path).resolve()
    if not path.exists():
        print(f"错误：找不到图片文件：{path}", file=sys.stderr)
        sys.exit(1)

    # 读取并编码为 base64 data URL
    suffix = path.suffix.lower()
    mime_types = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
    }
    mime = mime_types.get(suffix, "image/png")

    with open(path, "rb") as f:
        data = base64.b64encode(f.read()).decode("utf-8")
    return f"data:{mime};base64,{data}"


def get_image_dimensions(filepath: Path) -> Optional[Tuple[int, int]]:
    """读取图片文件头获取实际像素尺寸（支持 JPEG/PNG，无需第三方库）。"""
    try:
        with open(filepath, "rb") as f:
            header = f.read(32)

            # PNG: 固定头 + IHDR 块中包含宽高
            if header[:8] == b"\x89PNG\r\n\x1a\n":
                w = struct.unpack(">I", header[16:20])[0]
                h = struct.unpack(">I", header[20:24])[0]
                return (w, h)

            # JPEG: 需要找 SOF 标记
            if header[:2] == b"\xff\xd8":
                f.seek(2)
                while True:
                    marker = f.read(2)
                    if len(marker) < 2:
                        break
                    if marker[0] != 0xFF:
                        break
                    # SOF0-SOF15（排除 DHT、SOS 等）
                    if marker[1] in (0xC0, 0xC1, 0xC2):
                        length_data = f.read(2)
                        precision = f.read(1)
                        h = struct.unpack(">H", f.read(2))[0]
                        w = struct.unpack(">H", f.read(2))[0]
                        return (w, h)
                    else:
                        length_data = f.read(2)
                        if len(length_data) < 2:
                            break
                        length = struct.unpack(">H", length_data)[0]
                        f.seek(length - 2, 1)
    except Exception:
        pass
    return None


def format_file_size(size_bytes: int) -> str:
    """将字节数格式化为可读的文件大小。"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.2f} MB"


def create_ssl_context() -> ssl.SSLContext:
    """创建 SSL 上下文，优先使用系统证书验证。"""
    ctx = ssl.create_default_context()
    return ctx


def api_request(api_key: str, payload: dict) -> dict:
    """发送 API 请求，支持自动重试。"""
    data = json.dumps(payload).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "User-Agent": "OpenClaw-Seedream-Skill/1.0",
    }

    last_error = None
    ssl_ctx = create_ssl_context()

    for attempt in range(MAX_RETRIES + 1):
        try:
            req = urllib.request.Request(API_BASE, data=data, headers=headers)
            with urllib.request.urlopen(req, timeout=300, context=ssl_ctx) as resp:
                return json.loads(resp.read())

        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8", errors="replace")
            try:
                error_data = json.loads(error_body)
                error_msg = error_data.get("error", {}).get("message", error_body)
                error_code = error_data.get("error", {}).get("code", str(e.code))
            except (json.JSONDecodeError, KeyError):
                error_msg = error_body[:500]
                error_code = str(e.code)

            last_error = f"接口错误 ({error_code}): {error_msg}"

            # 客户端错误（4xx）不重试，429（限频）除外
            if 400 <= e.code < 500 and e.code != 429:
                break

        except urllib.error.URLError as e:
            last_error = f"连接错误: {e.reason}"
            # 首次 SSL 证书验证失败时，降级为不验证模式
            if attempt == 0 and "CERTIFICATE_VERIFY_FAILED" in str(e.reason):
                ssl_ctx = ssl.create_default_context()
                ssl_ctx.check_hostname = False
                ssl_ctx.verify_mode = ssl.CERT_NONE
                print("警告：SSL 证书验证失败，正在以不验证模式重试...", file=sys.stderr)
                continue

        except Exception as e:
            last_error = f"请求失败: {e}"

        if attempt < MAX_RETRIES:
            wait = RETRY_DELAY * (attempt + 1)
            print(f"  {wait} 秒后重试...（第 {attempt + 2}/{MAX_RETRIES + 1} 次）", file=sys.stderr)
            time.sleep(wait)

    raise Exception(last_error)


def download_image(url: str, output_path: Path) -> None:
    """从 URL 下载图片到本地文件。"""
    ssl_ctx = create_ssl_context()
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "OpenClaw-Seedream-Skill/1.0"})
        with urllib.request.urlopen(req, timeout=120, context=ssl_ctx) as resp:
            with open(output_path, "wb") as f:
                f.write(resp.read())
    except urllib.error.URLError:
        # SSL 失败时降级重试
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE
        req = urllib.request.Request(url, headers={"User-Agent": "OpenClaw-Seedream-Skill/1.0"})
        with urllib.request.urlopen(req, timeout=120, context=ssl_ctx) as resp:
            with open(output_path, "wb") as f:
                f.write(resp.read())


# ============================================================
# 主程序
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="使用 Seedream API 生成图片",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  %(prog)s --prompt "日落风景" --filename "日落.png"
  %(prog)s --prompt "电影感画面" --filename "分镜.png" --aspect 16:9
  %(prog)s --prompt "修改背景" --filename "编辑.png" --input-image "原图.png" --model seededit-3.0
  %(prog)s --prompt "同一角色" --filename "场景.png" --ref-images "角色1.png" "角色2.png"
        """,
    )

    parser.add_argument("--prompt", "-p", required=True, help="图片描述或编辑指令")
    parser.add_argument("--filename", "-f", required=True, help="输出文件名（如 scene01.png）")
    parser.add_argument(
        "--model", "-m",
        default="seedream-5.0",
        choices=list(MODEL_MAP.keys()),
        help="使用的模型（默认：seedream-5.0）",
    )
    parser.add_argument("--size", "-s", default="2K", help="分辨率：1K、2K、4K、adaptive，或精确像素如 1920x1080")
    parser.add_argument(
        "--aspect", "-a",
        choices=list(ASPECT_RATIOS.keys()),
        help="画面比例预设（会覆盖 --size 的尺寸）",
    )
    parser.add_argument("--count", "-c", type=int, default=1, help="生成数量（1-4 张）")
    parser.add_argument("--input-image", "-i", help="输入图片 URL 或本地路径，用于图生图编辑")
    parser.add_argument("--ref-images", "-r", nargs="+", help="参考图路径，用于角色融合（最多 10 张）")
    parser.add_argument("--seed", type=int, help="随机种子，用于复现结果")
    parser.add_argument("--guidance", type=float, help="引导系数（1.0-20.0）")
    parser.add_argument("--no-watermark", action="store_true", help="关闭隐形水印")

    args = parser.parse_args()

    # 参数校验
    if args.count < 1 or args.count > 4:
        print("错误：--count 必须在 1 到 4 之间。", file=sys.stderr)
        sys.exit(1)

    api_key = get_api_key()

    # 构建请求参数
    model_id = MODEL_MAP.get(args.model, args.model)
    size = resolve_size(args.size, args.aspect)

    payload = {
        "model": model_id,
        "prompt": args.prompt,
        "response_format": "url",
        "watermark": not args.no_watermark,
    }

    if size:
        payload["size"] = size
    if args.seed is not None:
        payload["seed"] = args.seed
    if args.guidance is not None:
        payload["guidance_scale"] = args.guidance

    # 处理图片输入
    if args.ref_images:
        # 多图融合：传入图片 URL 数组
        image_urls = [image_to_url(img) for img in args.ref_images]
        if args.input_image:
            image_urls.insert(0, image_to_url(args.input_image))
        payload["image"] = image_urls
        print(f"使用 {len(image_urls)} 张参考图进行角色融合")
    elif args.input_image:
        # 单图编辑
        payload["image"] = image_to_url(args.input_image)
        print(f"使用输入图片进行编辑：{args.input_image}")

    # 批量生成
    if args.count > 1:
        payload["sequential_image_generation"] = "auto"
        payload["sequential_image_generation_options"] = {"max_images": args.count}

    # 准备输出路径
    output_path = Path(args.filename)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 开始生成
    aspect_info = f"（{args.aspect}）" if args.aspect else ""
    size_info = size or "默认"
    print(f"正在生成 | 模型：{args.model} | 尺寸：{size_info}{aspect_info} | 数量：{args.count}")
    print(f"提示词：{args.prompt[:100]}{'...' if len(args.prompt) > 100 else ''}")
    print()

    start_time = time.time()

    try:
        result = api_request(api_key, payload)
    except Exception as e:
        print(f"错误：{e}", file=sys.stderr)
        sys.exit(1)

    elapsed = time.time() - start_time

    # 检查错误
    if "error" in result:
        error = result["error"]
        print(f"错误：{error.get('message', '未知错误')}", file=sys.stderr)
        sys.exit(1)

    data = result.get("data")
    if not data or not isinstance(data, list) or len(data) == 0:
        print("错误：API 返回中没有图片数据。", file=sys.stderr)
        print(f"响应内容：{json.dumps(result, ensure_ascii=False)[:500]}", file=sys.stderr)
        sys.exit(1)

    # 下载图片
    saved_files = []
    for idx, item in enumerate(data):
        if "error" in item:
            print(f"警告：第 {idx + 1} 张图片生成失败：{item['error'].get('message', '未知')}", file=sys.stderr)
            continue

        image_url = item.get("url")
        if not image_url:
            print(f"警告：第 {idx + 1} 张图片没有 URL。", file=sys.stderr)
            continue

        if len(data) == 1:
            save_path = output_path
        else:
            stem = output_path.stem
            suffix = output_path.suffix or ".png"
            save_path = output_path.parent / f"{stem}_{idx + 1:03d}{suffix}"

        print(f"正在下载第 {idx + 1}/{len(data)} 张图片...")
        try:
            download_image(image_url, save_path)
            full_path = save_path.resolve()
            file_size = full_path.stat().st_size
            dimensions = get_image_dimensions(full_path)
            saved_files.append({
                "path": full_path,
                "size": file_size,
                "dimensions": dimensions,
            })
            dim_str = f"{dimensions[0]}x{dimensions[1]}" if dimensions else "未知"
            print(f"  已保存：{full_path}")
            print(f"  尺寸：{dim_str} | 文件大小：{format_file_size(file_size)}")
        except Exception as e:
            print(f"  警告：第 {idx + 1} 张下载失败：{e}", file=sys.stderr)

    # 输出结果
    print()
    if saved_files:
        print(f"=== 生成完成 ===")
        print(f"模型：{args.model}（{model_id}）")
        print(f"数量：{len(saved_files)} 张 | 耗时：{elapsed:.1f} 秒")
        if saved_files[0]["dimensions"]:
            w, h = saved_files[0]["dimensions"]
            print(f"实际像素：{w}x{h}")
        print()
        for item in saved_files:
            print(f"MEDIA: {item['path']}")
    else:
        print("错误：没有图片被保存。", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
