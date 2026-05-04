"""
HappyHorse ComfyUI 节点 - 工具函数
包含：配置读写、Tensor/PIL 转换、OSS 上传、API 调用与轮询、视频下载
"""

import os
import io
import json
import time
import uuid
import requests
import numpy as np
from PIL import Image


# 当前插件目录
PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(PLUGIN_DIR, "config.json")

# 视频输出本地目录（位于 ComfyUI 根目录下的 output/happyhorse）
try:
    import folder_paths
    OUTPUT_DIR = os.path.join(folder_paths.get_output_directory(), "happyhorse")
except Exception:
    OUTPUT_DIR = os.path.join(PLUGIN_DIR, "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)


# ------------------------- 配置读写 -------------------------

def load_config() -> dict:
    """读取 config.json"""
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[HappyHorse] 读取 config.json 失败: {e}")
        return {}


def save_config(data: dict) -> None:
    """保存 config.json（保留原有其他字段）"""
    cfg = load_config()
    cfg.update(data)
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"[HappyHorse] 保存 config.json 失败: {e}")


def get_default_api_key() -> str:
    """从 config.json 或环境变量中获取默认 API Key"""
    cfg = load_config()
    key = cfg.get("api_key", "") or ""
    if not key or key.startswith("Your"):
        key = os.getenv("DASHSCOPE_API_KEY", "") or ""
    return key


def resolve_api_key(api_key: str) -> str:
    """
    解析最终使用的 api_key：
      - 如果用户传入值，使用并写回 config.json
      - 否则使用 config.json 中的值
    """
    api_key = (api_key or "").strip()
    if api_key:
        save_config({"api_key": api_key})
        return api_key
    return get_default_api_key()


def get_oss_default(field: str) -> str:
    """读取 config.json 中指定 OSS 字段的默认值"""
    cfg = load_config()
    return cfg.get(field, "") or ""


def resolve_oss_config(access_key: str = "", secret_key: str = "",
                       bucket: str = "", endpoint: str = "") -> dict:
    """
    解析最终使用的 OSS 配置：
      - 节点传入的非空字段会覆盖并保存到 config.json
      - 空字段沿用 config.json 中的值
    返回包含 OSS_ACCESS_KEY / OSS_SECRET_KEY / bucket / endpoint 的字典。
    如果任一字段最终为空，抓取时 _get_oss_bucket() 会抛错。
    """
    update = {}
    ak = (access_key or "").strip()
    sk = (secret_key or "").strip()
    bk = (bucket or "").strip()
    ep = (endpoint or "").strip()
    if ak:
        update["OSS_ACCESS_KEY"] = ak
    if sk:
        update["OSS_SECRET_KEY"] = sk
    if bk:
        update["bucket"] = bk
    if ep:
        update["endpoint"] = ep
    if update:
        save_config(update)
    cfg = load_config()
    return {
        "OSS_ACCESS_KEY": cfg.get("OSS_ACCESS_KEY", "") or "",
        "OSS_SECRET_KEY": cfg.get("OSS_SECRET_KEY", "") or "",
        "bucket": cfg.get("bucket", "") or "",
        "endpoint": cfg.get("endpoint", "") or "",
    }


# ------------------------- Tensor/PIL 转换 -------------------------

def tensor_to_pil(tensor) -> Image.Image:
    """
    将单张 ComfyUI IMAGE tensor (1,H,W,C) / (H,W,C) 转为 PIL Image
    """
    if hasattr(tensor, "is_cuda") and tensor.is_cuda:
        tensor = tensor.cpu()

    arr = tensor.detach().numpy() if hasattr(tensor, "detach") else np.asarray(tensor)
    if arr.ndim == 4:
        arr = arr[0]
    arr = np.clip(arr * 255.0, 0, 255).astype(np.uint8)
    return Image.fromarray(arr)


def iter_images_from_batch(images):
    """
    从 ComfyUI IMAGE batch 张量 (B,H,W,C) 中逐张转换为 PIL
    """
    if images is None:
        return
    if hasattr(images, "is_cuda") and images.is_cuda:
        images = images.cpu()
    if images.ndim == 3:
        images = images.unsqueeze(0)
    n = images.shape[0]
    for i in range(n):
        arr = images[i].detach().numpy() if hasattr(images, "detach") else np.asarray(images[i])
        arr = np.clip(arr * 255.0, 0, 255).astype(np.uint8)
        yield Image.fromarray(arr)


# ------------------------- OSS 上传 -------------------------

def _get_oss_bucket():
    """根据 config.json 初始化 OSS bucket"""
    try:
        import oss2  # type: ignore
    except ImportError:
        raise RuntimeError("未安装 oss2，请执行 pip install oss2")

    cfg = load_config()
    ak = cfg.get("OSS_ACCESS_KEY") or os.getenv("OSS_ACCESS_KEY")
    sk = cfg.get("OSS_SECRET_KEY") or os.getenv("OSS_SECRET_KEY")
    bucket_name = cfg.get("bucket")
    endpoint = cfg.get("endpoint", "oss-cn-hangzhou.aliyuncs.com")

    if not (ak and sk and bucket_name):
        raise RuntimeError("OSS 配置不完整，请在 config.json 中填写 OSS_ACCESS_KEY / OSS_SECRET_KEY / bucket / endpoint")

    auth = oss2.Auth(ak, sk)
    bucket = oss2.Bucket(auth, endpoint, bucket_name)
    return bucket, bucket_name, endpoint


def upload_pil_to_oss(image: Image.Image, object_name: str = None) -> str:
    """把 PIL 图片上传到 OSS，返回公网 URL"""
    bucket, bucket_name, endpoint = _get_oss_bucket()

    if object_name is None:
        object_name = f"happyhorse/{uuid.uuid4().hex}.png"

    buf = io.BytesIO()
    image.save(buf, format="PNG")
    buf.seek(0)
    bucket.put_object(object_name, buf)

    return f"https://{bucket_name}.{endpoint}/{object_name}"


def upload_file_to_oss(file_path: str, object_name: str = None) -> str:
    """把本地文件上传到 OSS，返回公网 URL"""
    bucket, bucket_name, endpoint = _get_oss_bucket()

    if object_name is None:
        ext = os.path.splitext(file_path)[1] or ".bin"
        object_name = f"happyhorse/{uuid.uuid4().hex}{ext}"

    bucket.put_object_from_file(object_name, file_path)
    return f"https://{bucket_name}.{endpoint}/{object_name}"


def resolve_video_input(video: str) -> str:
    """
    视频输入解析：
      - 若是 http(s) URL，原样返回
      - 否则视为本地路径，上传到 OSS，返回 URL
    """
    if not video:
        raise ValueError("视频输入为空")
    v = video.strip()
    if v.lower().startswith(("http://", "https://")):
        return v
    if not os.path.isfile(v):
        raise FileNotFoundError(f"视频文件不存在: {v}")
    return upload_file_to_oss(v)


# ------------------------- DashScope 视频生成 API -------------------------

API_URL_DEFAULT = "https://dashscope.aliyuncs.com/api/v1/services/aigc/video-generation/video-synthesis"
TASK_URL_DEFAULT = "https://dashscope.aliyuncs.com/api/v1/tasks"


def _api_endpoints():
    cfg = load_config()
    api_url = cfg.get("base_url") or API_URL_DEFAULT
    task_url = cfg.get("task_url") or TASK_URL_DEFAULT
    # 容错：如果 base_url 是 compatible-mode 的地址，回退到官方端点
    if "compatible-mode" in api_url:
        api_url = API_URL_DEFAULT
    return api_url, task_url


def create_task(api_key: str, payload: dict) -> str:
    """提交视频生成任务，返回 task_id"""
    api_url, _ = _api_endpoints()
    headers = {
        "X-DashScope-Async": "enable",
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    print(f"[HappyHorse] POST {api_url}")
    print(f"[HappyHorse] payload: {json.dumps(payload, ensure_ascii=False)}")

    resp = requests.post(api_url, headers=headers, json=payload, timeout=30)
    try:
        data = resp.json()
    except Exception:
        raise RuntimeError(f"创建任务失败，HTTP {resp.status_code}: {resp.text}")

    if resp.status_code != 200 or "output" not in data or "task_id" not in data.get("output", {}):
        code = data.get("code", "UnknownError")
        message = data.get("message", resp.text)
        raise RuntimeError(f"创建任务失败: {code} - {message}")

    task_id = data["output"]["task_id"]
    print(f"[HappyHorse] 任务创建成功 task_id={task_id}")
    return task_id


def poll_task(api_key: str, task_id: str, interval: float = 15.0, timeout: float = 1200.0) -> str:
    """轮询任务结果，成功时返回 video_url"""
    _, task_url = _api_endpoints()
    url = f"{task_url}/{task_id}"
    headers = {"Authorization": f"Bearer {api_key}"}

    start = time.time()
    while True:
        if time.time() - start > timeout:
            raise TimeoutError(f"任务轮询超时（{timeout}s），task_id={task_id}")

        try:
            resp = requests.get(url, headers=headers, timeout=30)
            data = resp.json()
        except Exception as e:
            print(f"[HappyHorse] 查询异常: {e}，稍后重试...")
            time.sleep(interval)
            continue

        output = data.get("output", {})
        status = output.get("task_status", "UNKNOWN")
        print(f"[HappyHorse] 任务状态: {status}")

        if status == "SUCCEEDED":
            video_url = output.get("video_url")
            if not video_url:
                raise RuntimeError("任务成功但未返回 video_url")
            return video_url
        if status in ("FAILED", "CANCELED", "UNKNOWN"):
            code = output.get("code", "")
            message = output.get("message", "")
            raise RuntimeError(f"任务{status}: {code} - {message}")

        time.sleep(interval)


def download_video(url: str, save_dir: str = None) -> str:
    """下载视频到本地，返回本地路径"""
    save_dir = save_dir or OUTPUT_DIR
    os.makedirs(save_dir, exist_ok=True)
    filename = f"happyhorse_{int(time.time())}_{uuid.uuid4().hex[:8]}.mp4"
    local_path = os.path.join(save_dir, filename)

    try:
        with requests.get(url, stream=True, timeout=120) as r:
            r.raise_for_status()
            with open(local_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=1024 * 256):
                    if chunk:
                        f.write(chunk)
        print(f"[HappyHorse] 视频已保存: {local_path}")
        return local_path
    except Exception as e:
        print(f"[HappyHorse] 视频下载失败: {e}")
        return ""


def run_video_task(api_key: str, payload: dict) -> tuple:
    """一站式：提交 + 轮询 + 下载，返回 (video_url, local_path)"""
    task_id = create_task(api_key, payload)
    video_url = poll_task(api_key, task_id)
    local_path = download_video(video_url)
    return video_url, local_path


# ------------------------- UI 视频预览信息 -------------------------

def build_video_ui_info(local_path: str, frame_rate: int = 16) -> dict:
    """
    根据视频本地路径，构造 ComfyUI 前端可识别的视频预览描述。
    返回形如: {"filename": ..., "subfolder": ..., "type": "output", "format": "video/mp4", "frame_rate": 16}
    """
    filename = os.path.basename(local_path) if local_path else ""
    subfolder = "happyhorse"
    try:
        import folder_paths  # type: ignore
        output_dir = folder_paths.get_output_directory()
        if local_path and os.path.commonpath([os.path.abspath(local_path), os.path.abspath(output_dir)]) == os.path.abspath(output_dir):
            rel = os.path.relpath(local_path, output_dir)
            subfolder = os.path.dirname(rel).replace("\\", "/")
            filename = os.path.basename(rel)
    except Exception:
        pass
    return {
        "filename": filename,
        "subfolder": subfolder,
        "type": "output",
        "format": "video/mp4",
        "frame_rate": frame_rate,
    }
