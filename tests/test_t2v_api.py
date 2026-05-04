"""
通过 ComfyUI HTTP API 提交 T2V 工作流并验证视频播放。
步骤：
  1. POST /prompt 提交工作流
  2. 轮询 /history/{prompt_id}
  3. 从 outputs.gifs 读取 filename/subfolder
  4. HEAD /view?filename=...&subfolder=...&type=output 验证视频可访问
"""

import json
import os
import sys
import time
import uuid
import urllib.request
import urllib.error

HOST = "http://127.0.0.1:8188"
CLIENT_ID = uuid.uuid4().hex


def http_post(url: str, data: dict, timeout: float = 30.0):
    body = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def http_get_json(url: str, timeout: float = 30.0):
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def http_head(url: str, timeout: float = 30.0):
    req = urllib.request.Request(url, method="HEAD")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, dict(resp.headers)


def build_prompt():
    return {
        "1": {
            "class_type": "HappyHorse T2V",
            "inputs": {
                "api_key": "",
                "prompt": "一匹白色的骏马在金色的草原上自由奔跑，夕阳西下，尘土飞扬，电影级画面",
                "resolution": "720P",
                "ratio": "16:9",
                "duration": 5,
                "seed": 0,
                "watermark": True,
            },
        }
    }


def main():
    # 1. ping server
    print(f"[1/4] 检查 ComfyUI 服务: {HOST}")
    try:
        info = http_get_json(f"{HOST}/system_stats", timeout=5)
        print(f"    ComfyUI 运行中，Python {info.get('system', {}).get('python_version','?')[:30]}...")
    except Exception as e:
        print(f"    ERROR: ComfyUI 未响应: {e}")
        sys.exit(1)

    # 2. 提交任务
    print("[2/4] 提交 T2V 工作流")
    prompt = build_prompt()
    resp = http_post(f"{HOST}/prompt", {"prompt": prompt, "client_id": CLIENT_ID})
    prompt_id = resp.get("prompt_id")
    print(f"    prompt_id = {prompt_id}")
    if not prompt_id:
        print(f"    ERROR: 提交失败: {resp}")
        sys.exit(2)

    # 3. 轮询 history
    print("[3/4] 轮询任务结果（超时 25 分钟）...")
    start = time.time()
    timeout = 25 * 60
    interval = 10
    outputs = None
    while True:
        if time.time() - start > timeout:
            print(f"    ERROR: 等待超时")
            sys.exit(3)

        try:
            hist = http_get_json(f"{HOST}/history/{prompt_id}", timeout=15)
        except Exception as e:
            print(f"    [warn] history 查询异常: {e}")
            time.sleep(interval)
            continue

        if prompt_id in hist:
            entry = hist[prompt_id]
            status = entry.get("status", {})
            status_str = status.get("status_str", "unknown")
            completed = status.get("completed", False)
            print(f"    status={status_str} completed={completed}  已等待 {int(time.time()-start)}s")
            if completed or status_str in ("success", "error"):
                outputs = entry.get("outputs", {})
                if status_str == "error":
                    msgs = status.get("messages", [])
                    print(f"    ERROR: 任务失败: {json.dumps(msgs, ensure_ascii=False)[:500]}")
                    sys.exit(4)
                break
        else:
            print(f"    ...排队中 (elapsed {int(time.time()-start)}s)")

        time.sleep(interval)

    # 4. 验证视频
    print("[4/4] 解析输出并验证视频可播放")
    print(f"    outputs keys: {list(outputs.keys())}")
    node_out = outputs.get("1", {})
    print(f"    node '1' output keys: {list(node_out.keys())}")
    print(f"    raw output: {json.dumps(node_out, ensure_ascii=False)[:800]}")

    gifs = node_out.get("gifs", [])
    if not gifs:
        print("    ERROR: outputs 中没有 gifs 字段（视频不会在 UI 播放）")
        sys.exit(5)

    info = gifs[0]
    print(f"    视频预览信息: {info}")
    filename = info.get("filename")
    subfolder = info.get("subfolder", "")
    ftype = info.get("type", "output")
    fmt = info.get("format", "")

    # 构造 /view 访问 URL
    import urllib.parse as up
    qs = up.urlencode({"filename": filename, "subfolder": subfolder, "type": ftype})
    view_url = f"{HOST}/view?{qs}"
    print(f"    视频播放地址: {view_url}")

    try:
        status, headers = http_head(view_url)
        size = headers.get("Content-Length", "?")
        ctype = headers.get("Content-Type", "?")
        print(f"    HEAD -> HTTP {status}, Content-Type={ctype}, Content-Length={size}")
        if status != 200:
            print(f"    ERROR: 视频无法访问")
            sys.exit(6)
    except Exception as e:
        print(f"    ERROR: HEAD 请求失败: {e}")
        sys.exit(7)

    # 打印原始 text（包含 video_url/video_path）
    texts = node_out.get("text", [])
    if texts:
        print(f"    text 输出: {texts[0]}")

    print("\n✅ 测试通过：视频已生成并可通过 ComfyUI /view 接口播放")
    print(f"   浏览器直接访问：{view_url}")


if __name__ == "__main__":
    main()
