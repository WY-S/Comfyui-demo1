"""
HappyHorse ComfyUI 自定义节点
- HappyHorse 文生视频  (happyhorse-1.0-t2v)
- HappyHorse 图生视频  (happyhorse-1.0-i2v)
- HappyHorse 参考生视频 (happyhorse-1.0-r2v)
- HappyHorse 视频编辑  (happyhorse-1.0-video-edit)
"""

from .utils import (
    get_default_api_key,
    resolve_api_key,
    tensor_to_pil,
    iter_images_from_batch,
    upload_pil_to_oss,
    resolve_video_input,
    run_video_task,
    build_video_ui_info,
    get_oss_default,
    resolve_oss_config,
)

# 尝试导入 ComfyUI 原生 VIDEO 类型（ComfyUI 0.3.30+ / 0.20+）
try:
    from comfy_api.input_impl import VideoFromFile  # type: ignore
except Exception:
    VideoFromFile = None


def _make_video_object(local_path: str):
    """批本地视频路径包装为 ComfyUI 原生 VIDEO 对象；不可用时返回 None"""
    if VideoFromFile is None or not local_path:
        return None
    try:
        return VideoFromFile(local_path)
    except Exception as e:
        print(f"[HappyHorse] VideoFromFile 创建失败: {e}")
        return None


CATEGORY_NAME = "HappyHorse"


# ------------------------- 文生视频 -------------------------

class HappyHorseT2V:
    """HappyHorse 文生视频"""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "api_key": ("STRING", {
                    "multiline": False,
                    "default": get_default_api_key(),
                    "tooltip": "阿里百炼 API Key（填写后自动保存到 config.json）",
                }),
                "prompt": ("STRING", {
                    "multiline": True,
                    "default": "",
                    "tooltip": "文本提示词，描述要生成的视频内容",
                }),
                "resolution": (["720P", "1080P"], {"default": "1080P"}),
                "ratio": (["16:9", "9:16", "1:1", "4:3", "3:4"], {"default": "16:9"}),
                "duration": ("INT", {"default": 5, "min": 3, "max": 15, "step": 1}),
                "seed": ("INT", {"default": 0, "min": 0, "max": 2147483647}),
                "watermark": ("BOOLEAN", {"default": True, "tooltip": "是否添加 Happy Horse 水印"}),
            },
        }

    RETURN_TYPES = ("VIDEO", "STRING", "STRING")
    RETURN_NAMES = ("video", "video_url", "video_path")
    FUNCTION = "action"
    CATEGORY = CATEGORY_NAME
    OUTPUT_NODE = True

    def action(self, api_key, prompt, resolution, ratio, duration, seed, watermark):
        api_key = resolve_api_key(api_key)
        if not api_key:
            raise ValueError("缺少 api_key")
        if not prompt or not prompt.strip():
            raise ValueError("prompt 不能为空")

        payload = {
            "model": "happyhorse-1.0-t2v",
            "input": {"prompt": prompt},
            "parameters": {
                "resolution": resolution,
                "ratio": ratio,
                "duration": int(duration),
                "watermark": bool(watermark),
                "seed": int(seed),
            },
        }

        video_url, local_path = run_video_task(api_key, payload)
        video_obj = _make_video_object(local_path)
        ui = {
            "gifs": [build_video_ui_info(local_path)],
            "text": [f"video_url: {video_url}\nvideo_path: {local_path}"],
        }
        return {"ui": ui, "result": (video_obj, video_url, local_path)}


# ------------------------- 图生视频 -------------------------

class HappyHorseI2V:
    """HappyHorse 图生视频（首帧）"""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "api_key": ("STRING", {
                    "multiline": False,
                    "default": get_default_api_key(),
                    "tooltip": "阿里百炼 API Key（填写后自动保存到 config.json）",
                }),
                "image": ("IMAGE", {"tooltip": "首帧图像"}),
                "prompt": ("STRING", {"multiline": True, "default": ""}),
                "resolution": (["720P", "1080P"], {"default": "1080P"}),
                "duration": ("INT", {"default": 5, "min": 3, "max": 15, "step": 1}),
                "seed": ("INT", {"default": 0, "min": 0, "max": 2147483647}),
                "watermark": ("BOOLEAN", {"default": True}),
            },
            "optional": {
                "OSS_ACCESS_KEY": ("STRING", {
                    "multiline": False,
                    "default": get_oss_default("OSS_ACCESS_KEY"),
                    "tooltip": "阿里云 OSS AccessKey ID（留空使用 config.json 默认值）",
                }),
                "OSS_SECRET_KEY": ("STRING", {
                    "multiline": False,
                    "default": get_oss_default("OSS_SECRET_KEY"),
                    "tooltip": "阿里云 OSS AccessKey Secret（留空使用 config.json 默认值）",
                }),
                "bucket": ("STRING", {
                    "multiline": False,
                    "default": get_oss_default("bucket"),
                    "tooltip": "OSS Bucket 名称（留空使用 config.json 默认值）",
                }),
                "endpoint": ("STRING", {
                    "multiline": False,
                    "default": get_oss_default("endpoint"),
                    "tooltip": "OSS Endpoint，如 oss-cn-beijing.aliyuncs.com（留空使用 config.json 默认值）",
                }),
            },
        }

    RETURN_TYPES = ("VIDEO", "STRING", "STRING")
    RETURN_NAMES = ("video", "video_url", "video_path")
    FUNCTION = "action"
    CATEGORY = CATEGORY_NAME
    OUTPUT_NODE = True

    def action(self, api_key, image, prompt, resolution, duration, seed, watermark,
               OSS_ACCESS_KEY="", OSS_SECRET_KEY="", bucket="", endpoint=""):
        api_key = resolve_api_key(api_key)
        if not api_key:
            raise ValueError("缺少 api_key")

        # 解析 OSS 配置：节点传入的非空值会写回 config.json，否则用 config 默认值
        oss_cfg = resolve_oss_config(OSS_ACCESS_KEY, OSS_SECRET_KEY, bucket, endpoint)
        missing = [k for k, v in oss_cfg.items() if not v]

        if not missing:
            # ✅ OSS 配置齐全：走 I2V（上传首帧）
            pil = tensor_to_pil(image)
            first_frame_url = upload_pil_to_oss(pil)
            print(f"[HappyHorse] 首帧已上传: {first_frame_url}")

            payload = {
                "model": "happyhorse-1.0-i2v",
                "input": {
                    "prompt": prompt or "",
                    "media": [
                        {"type": "first_frame", "url": first_frame_url}
                    ],
                },
                "parameters": {
                    "resolution": resolution,
                    "duration": int(duration),
                    "watermark": bool(watermark),
                    "seed": int(seed),
                },
            }
        else:
            # ⚠️ OSS 配置不全：降级为文生视频 T2V（忽略图片，仅用 prompt）
            print(f"[HappyHorse] OSS 配置不完整（缺少 {missing}），跳过首帧上传，降级为文生视频 T2V")
            if not prompt or not prompt.strip():
                raise ValueError("OSS 未配置且 prompt 为空，无法生成视频。请配置 OSS 或填写 prompt。")
            payload = {
                "model": "happyhorse-1.0-t2v",
                "input": {"prompt": prompt},
                "parameters": {
                    "resolution": resolution,
                    "ratio": "16:9",
                    "duration": int(duration),
                    "watermark": bool(watermark),
                    "seed": int(seed),
                },
            }

        video_url, local_path = run_video_task(api_key, payload)
        video_obj = _make_video_object(local_path)
        ui = {
            "gifs": [build_video_ui_info(local_path)],
            "text": [f"video_url: {video_url}\nvideo_path: {local_path}"],
        }
        return {"ui": ui, "result": (video_obj, video_url, local_path)}


# ------------------------- 参考生视频 -------------------------

class HappyHorseR2V:
    """HappyHorse 参考生视频（多张参考图）"""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "api_key": ("STRING", {
                    "multiline": False,
                    "default": get_default_api_key(),
                    "tooltip": "阿里百炼 API Key（填写后自动保存到 config.json）",
                }),
                "reference_images": ("IMAGE", {
                    "tooltip": "参考图（支持 batch 传入多张，1~9 张）。prompt 中通过 [Image 1]、[Image 2]... 引用",
                }),
                "prompt": ("STRING", {"multiline": True, "default": ""}),
                "resolution": (["720P", "1080P"], {"default": "1080P"}),
                "ratio": (["16:9", "9:16", "1:1", "4:3", "3:4"], {"default": "16:9"}),
                "duration": ("INT", {"default": 5, "min": 3, "max": 15, "step": 1}),
                "seed": ("INT", {"default": 0, "min": 0, "max": 2147483647}),
                "watermark": ("BOOLEAN", {"default": True}),
            },
            "optional": {
                "OSS_ACCESS_KEY": ("STRING", {
                    "multiline": False,
                    "default": get_oss_default("OSS_ACCESS_KEY"),
                    "tooltip": "阿里云 OSS AccessKey ID（留空使用 config.json 默认值）",
                }),
                "OSS_SECRET_KEY": ("STRING", {
                    "multiline": False,
                    "default": get_oss_default("OSS_SECRET_KEY"),
                    "tooltip": "阿里云 OSS AccessKey Secret（留空使用 config.json 默认值）",
                }),
                "bucket": ("STRING", {
                    "multiline": False,
                    "default": get_oss_default("bucket"),
                    "tooltip": "OSS Bucket 名称（留空使用 config.json 默认值）",
                }),
                "endpoint": ("STRING", {
                    "multiline": False,
                    "default": get_oss_default("endpoint"),
                    "tooltip": "OSS Endpoint，如 oss-cn-beijing.aliyuncs.com（留空使用 config.json 默认值）",
                }),
            },
        }

    RETURN_TYPES = ("VIDEO", "STRING", "STRING")
    RETURN_NAMES = ("video", "video_url", "video_path")
    FUNCTION = "action"
    CATEGORY = CATEGORY_NAME
    OUTPUT_NODE = True

    def action(self, api_key, reference_images, prompt, resolution, ratio, duration, seed, watermark,
               OSS_ACCESS_KEY="", OSS_SECRET_KEY="", bucket="", endpoint=""):
        api_key = resolve_api_key(api_key)
        if not api_key:
            raise ValueError("缺少 api_key")
        if not prompt or not prompt.strip():
            raise ValueError("prompt 不能为空")

        # 解析 OSS 配置：节点传入的非空值会写回 config.json，否则用 config 默认值
        oss_cfg = resolve_oss_config(OSS_ACCESS_KEY, OSS_SECRET_KEY, bucket, endpoint)
        missing = [k for k, v in oss_cfg.items() if not v]

        if not missing:
            # ✅ OSS 配置齐全：走 R2V（上传全部参考图）
            media = []
            for idx, pil in enumerate(iter_images_from_batch(reference_images), start=1):
                url = upload_pil_to_oss(pil)
                print(f"[HappyHorse] 参考图 {idx} 已上传: {url}")
                media.append({"type": "reference_image", "url": url})

            if not (1 <= len(media) <= 9):
                raise ValueError(f"参考图数量必须在 1~9 张之间，当前 {len(media)} 张")

            payload = {
                "model": "happyhorse-1.0-r2v",
                "input": {"prompt": prompt, "media": media},
                "parameters": {
                    "resolution": resolution,
                    "ratio": ratio,
                    "duration": int(duration),
                    "watermark": bool(watermark),
                    "seed": int(seed),
                },
            }
        else:
            # ⚠️ OSS 配置不全：降级为文生视频 T2V（忽略参考图）
            print(f"[HappyHorse] OSS 配置不完整（缺少 {missing}），跳过参考图上传，降级为文生视频 T2V")
            payload = {
                "model": "happyhorse-1.0-t2v",
                "input": {"prompt": prompt},
                "parameters": {
                    "resolution": resolution,
                    "ratio": ratio,
                    "duration": int(duration),
                    "watermark": bool(watermark),
                    "seed": int(seed),
                },
            }

        video_url, local_path = run_video_task(api_key, payload)
        video_obj = _make_video_object(local_path)
        ui = {
            "gifs": [build_video_ui_info(local_path)],
            "text": [f"video_url: {video_url}\nvideo_path: {local_path}"],
        }
        return {"ui": ui, "result": (video_obj, video_url, local_path)}


# ------------------------- 视频编辑 -------------------------

class HappyHorseVideoEdit:
    """HappyHorse 视频编辑（视频 + 参考图）"""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "api_key": ("STRING", {
                    "multiline": False,
                    "default": get_default_api_key(),
                    "tooltip": "阿里百炼 API Key（填写后自动保存到 config.json）",
                }),
                "video": ("STRING", {
                    "multiline": False,
                    "default": "",
                    "tooltip": "待编辑视频：公网 URL 或本地文件路径（本地路径需 OSS 配置齐全才能自动上传）",
                }),
                "prompt": ("STRING", {"multiline": True, "default": ""}),
                "resolution": (["720P", "1080P"], {"default": "1080P"}),
                "ratio": (["16:9", "9:16", "1:1", "4:3", "3:4"], {"default": "16:9"}),
                "seed": ("INT", {"default": 0, "min": 0, "max": 2147483647}),
                "watermark": ("BOOLEAN", {"default": True}),
            },
            "optional": {
                "reference_images": ("IMAGE", {
                    "tooltip": "参考图（可选，0~5 张，支持 batch）",
                }),
                "OSS_ACCESS_KEY": ("STRING", {
                    "multiline": False,
                    "default": get_oss_default("OSS_ACCESS_KEY"),
                    "tooltip": "阿里云 OSS AccessKey ID（留空使用 config.json 默认值）",
                }),
                "OSS_SECRET_KEY": ("STRING", {
                    "multiline": False,
                    "default": get_oss_default("OSS_SECRET_KEY"),
                    "tooltip": "阿里云 OSS AccessKey Secret（留空使用 config.json 默认值）",
                }),
                "bucket": ("STRING", {
                    "multiline": False,
                    "default": get_oss_default("bucket"),
                    "tooltip": "OSS Bucket 名称（留空使用 config.json 默认值）",
                }),
                "endpoint": ("STRING", {
                    "multiline": False,
                    "default": get_oss_default("endpoint"),
                    "tooltip": "OSS Endpoint，如 oss-cn-beijing.aliyuncs.com（留空使用 config.json 默认值）",
                }),
            },
        }

    RETURN_TYPES = ("VIDEO", "STRING", "STRING")
    RETURN_NAMES = ("video", "video_url", "video_path")
    FUNCTION = "action"
    CATEGORY = CATEGORY_NAME
    OUTPUT_NODE = True

    def action(self, api_key, video, prompt, resolution, ratio, seed, watermark,
               reference_images=None,
               OSS_ACCESS_KEY="", OSS_SECRET_KEY="", bucket="", endpoint=""):
        api_key = resolve_api_key(api_key)
        if not api_key:
            raise ValueError("缺少 api_key")
        if not prompt or not prompt.strip():
            raise ValueError("prompt 不能为空")
        if not video or not video.strip():
            raise ValueError("video 不能为空，请填写 URL 或本地文件路径")

        # 解析 OSS 配置
        oss_cfg = resolve_oss_config(OSS_ACCESS_KEY, OSS_SECRET_KEY, bucket, endpoint)
        missing = [k for k, v in oss_cfg.items() if not v]

        # 视频输入处理：URL 直接用；本地路径必须 OSS 齐全才能上传
        is_url = video.strip().lower().startswith(("http://", "https://"))
        if is_url:
            video_url_in = video.strip()
        else:
            if missing:
                raise ValueError(
                    f"视频为本地文件但 OSS 配置不完整（缺少 {missing}），无法上传。请提供视频 URL 或配置 OSS。"
                )
            video_url_in = resolve_video_input(video)
        print(f"[HappyHorse] 待编辑视频: {video_url_in}")

        media = [{"type": "video", "url": video_url_in}]

        # 可选参考图：OSS 齐全才上传，不全则跳过并警告
        if reference_images is not None:
            if missing:
                print(f"[HappyHorse] OSS 配置不完整（缺少 {missing}），跳过参考图上传，仅用视频 + prompt 编辑")
            else:
                for idx, pil in enumerate(iter_images_from_batch(reference_images), start=1):
                    url = upload_pil_to_oss(pil)
                    print(f"[HappyHorse] 参考图 {idx} 已上传: {url}")
                    media.append({"type": "reference_image", "url": url})
                ref_count = len(media) - 1
                if ref_count > 5:
                    raise ValueError(f"参考图最多 5 张，当前 {ref_count} 张")

        payload = {
            "model": "happyhorse-1.0-video-edit",
            "input": {"prompt": prompt, "media": media},
            "parameters": {
                "resolution": resolution,
                "ratio": ratio,
                "watermark": bool(watermark),
                "seed": int(seed),
            },
        }

        video_url, local_path = run_video_task(api_key, payload)
        video_obj = _make_video_object(local_path)
        ui = {
            "gifs": [build_video_ui_info(local_path)],
            "text": [f"video_url: {video_url}\nvideo_path: {local_path}"],
        }
        return {"ui": ui, "result": (video_obj, video_url, local_path)}


# ------------------------- 节点注册 -------------------------

NODE_CLASS_MAPPINGS = {
    "HappyHorse T2V": HappyHorseT2V,
    "HappyHorse I2V": HappyHorseI2V,
    "HappyHorse R2V": HappyHorseR2V,
    "HappyHorse VideoEdit": HappyHorseVideoEdit,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "HappyHorse T2V": "HappyHorse 文生视频",
    "HappyHorse I2V": "HappyHorse 图生视频",
    "HappyHorse R2V": "HappyHorse 参考生视频",
    "HappyHorse VideoEdit": "HappyHorse 视频编辑",
}
