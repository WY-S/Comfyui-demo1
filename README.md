# Comfyui-Wenyi-demo1 · HappyHorse 视频生成节点

基于阿里百炼 **HappyHorse** 视频生成 API 的 ComfyUI 自定义节点集。支持在 ComfyUI 画布中一键调用文生视频 / 图生视频 / 参考生视频 / 视频编辑能力，并在节点内直接内嵌播放生成结果。

---

## ✨ 功能特性

- 🎬 **四合一节点**：文生视频（T2V）、图生视频（I2V）、参考生视频（R2V）、视频编辑（VideoEdit）
- 📺 **内嵌播放**：节点输出视频直接在画布上预览播放，无需下载
- 🔌 **三端口输出**：`video`（ComfyUI 原生 VIDEO 类型）/ `video_url`（公网 URL）/ `video_path`（本地路径）
- ☁️ **OSS 可配置**：节点上直接填写 AccessKey / Secret / Bucket / Endpoint，支持运行时覆盖 `config.json`
- 🛡️ **优雅降级**：OSS 配置缺失时 I2V / R2V 自动降级为 T2V，不中断工作流
- 🔑 **配置持久化**：节点上填写的 `api_key` 和 OSS 凭证自动写回 `config.json`

---

## 📦 安装

### 方式一：Git Clone（推荐）

```bash
cd ComfyUI/custom_nodes
git clone <本仓库地址> Comfyui-Wenyi-demo1
cd Comfyui-Wenyi-demo1
pip install -r requirements.txt
```

### 方式二：ComfyUI Windows Portable 版

把本目录放到 `ComfyUI/custom_nodes/Comfyui-Wenyi-demo1/`，用内置 Python 安装依赖：

```powershell
# 先清除代理，避免 pip 安装超时
Remove-Item env:ALL_PROXY,env:HTTP_PROXY,env:HTTPS_PROXY,env:http_proxy,env:https_proxy -ErrorAction SilentlyContinue

./python_embeded/python.exe -m pip install -r ComfyUI/custom_nodes/Comfyui-Wenyi-demo1/requirements.txt
```

重启 ComfyUI，控制台出现如下字样即加载成功：

```
===== Comfyui-Wenyi-demo1 HappyHorse 节点已加载 =====
```

---

## 🔧 配置

### `config.json` 字段说明

```json
{
    "api_key": "sk-xxxxxxxxxxxxxxxxxxxxxxxx",
    "base_url": "https://dashscope.aliyuncs.com/api/v1/services/aigc/video-generation/video-synthesis",
    "task_url": "https://dashscope.aliyuncs.com/api/v1/tasks",
    "OSS_ACCESS_KEY": "LTAI5xxxxxxxxxxxxxxxx",
    "OSS_SECRET_KEY": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    "bucket": "your-bucket-name",
    "endpoint": "oss-cn-beijing.aliyuncs.com"
}
```

| 字段 | 说明 |
|---|---|
| `api_key` | 阿里百炼 [DashScope API Key](https://bailian.console.aliyun.com/) |
| `base_url` / `task_url` | 百炼视频生成异步接口（默认已填） |
| `OSS_ACCESS_KEY` / `OSS_SECRET_KEY` | 阿里云 RAM 账号 AK/SK，用于上传参考图 / 本地视频 |
| `bucket` | OSS Bucket 名称 |
| `endpoint` | OSS 区域域名，如 `oss-cn-beijing.aliyuncs.com`（必须与 bucket 所在区域一致） |

> 💡 **Endpoint 排查技巧**：若上传报 `AccessDenied`，响应 `details.Endpoint` 会直接告诉你正确的区域域名，替换即可。

### 节点内填写 vs `config.json`

所有节点都支持在 UI 上填写 `api_key` 和 4 个 OSS 字段。优先级规则：

- **节点填写非空** → 使用节点值并**自动写回 `config.json`**（持久化）
- **节点留空** → 使用 `config.json` 中的默认值

---

## 🎮 节点列表

所有节点分类位于 `Add Node → HappyHorse`。

### 1. HappyHorse 文生视频（T2V）

| 属性 | 内容 |
|---|---|
| 输入 | `prompt`（必填）/ `resolution` / `ratio` / `duration` / `seed` / `watermark` |
| 输出 | `video` / `video_url` / `video_path` |
| 特点 | 纯文本生成，无需参考素材，无需 OSS 配置 |

### 2. HappyHorse 图生视频（I2V）

| 属性 | 内容 |
|---|---|
| 输入 | `image`（IMAGE，首帧）+ `prompt` + OSS 配置 |
| 输出 | `video` / `video_url` / `video_path` |
| 降级 | OSS 未配置时忽略 image，仅用 prompt 降级为 T2V |

### 3. HappyHorse 参考生视频（R2V）

| 属性 | 内容 |
|---|---|
| 输入 | `reference_images`（IMAGE batch，1~9 张）+ `prompt` + OSS 配置 |
| Prompt 规范 | 用 `[Image 1]`、`[Image 2]`... 引用参考图 |
| 输出 | `video` / `video_url` / `video_path` |
| 降级 | OSS 未配置时忽略参考图，降级为 T2V |

### 4. HappyHorse 视频编辑（VideoEdit）

| 属性 | 内容 |
|---|---|
| 输入 | `video`（URL 或本地路径）+ `prompt` + 可选 `reference_images`（0~5 张） |
| 输出 | `video` / `video_url` / `video_path` |
| 降级 | video 是 URL 时即使 OSS 未配置也能执行（只跳过可选参考图）；video 是本地路径且 OSS 未配置时抛错 |

---

## 🚀 快速开始

`example_workflows/` 下提供 4 个开箱即用的测试工作流：

| 工作流文件 | 用途 | 包含节点 |
|---|---|---|
| `test_t2v.json` | 文生视频 | 仅 `HappyHorse T2V` |
| `test_i2v.json` | 图生视频 | `LoadImage → HappyHorse I2V` |
| `test_r2v.json` | 参考生视频 | `LoadImage × 2 → ImageBatch → HappyHorse R2V` |
| `test_video_edit.json` | 视频编辑 | 仅 `HappyHorse VideoEdit`（运行前请替换视频 URL） |

**打开方式**：ComfyUI 菜单 `Workflow → Open → 选择对应 json`，调整参数后按 `Ctrl + Enter` 运行。

---

## 📐 输出端口使用示例

每个节点都有 3 个输出：

```
┌─────────────────────────┐
│    HappyHorse T2V       │
│                         │
│         video  ──────── → 下游 VIDEO 处理节点（ComfyUI 原生 VIDEO 类型）
│     video_url  ──────── → 文本节点 / 保存到文件
│    video_path  ──────── → 本地 mp4 绝对路径
└─────────────────────────┘
```

- `video`：`VIDEO` 类型，可直接下游处理或预览
- `video_url`：阿里云返回的公网 mp4 URL（有效期约 24 小时）
- `video_path`：自动下载到 ComfyUI `output/happyhorse/` 下的本地路径

---

## 🐛 常见问题

### Q1. 节点输出端口显示不全或名称错乱？

**前端缓存问题**。ComfyUI 前端会缓存 `/object_info`，节点定义变更后需手动刷新：

- 方案 1：`F12 → Application → Local Storage → 清除站点数据 → Ctrl+Shift+R 硬刷新`
- 方案 2：画布上删除旧节点 → 重新 `Add Node` 添加
- 方案 3：打开无痕窗口访问 `http://127.0.0.1:8188`

### Q2. `oss2.exceptions.AccessDenied: The bucket you are attempting to access must be addressed using the specified endpoint`

OSS `endpoint` 配置错误。从错误详情的 `details.Endpoint` 字段复制正确域名到 `config.json`（或节点的 endpoint 字段）即可。

### Q3. ComfyUI 无 NVIDIA 显卡启动崩溃？

启动命令加 `--cpu` 参数：

```bash
python main.py --cpu
```

### Q4. `pip install` 一直超时？

ComfyUI Portable 版的 python_embeded 会继承系统代理，先清除代理环境变量再装：

```powershell
Remove-Item env:ALL_PROXY,env:HTTP_PROXY,env:HTTPS_PROXY,env:http_proxy,env:https_proxy -ErrorAction SilentlyContinue
./python_embeded/python.exe -m pip install -r requirements.txt
```

### Q5. Windows 终端输出 `UnicodeEncodeError: 'gbk' codec can't encode...`？

仅影响终端 emoji 打印，不影响视频生成。需要修复时在 PowerShell 执行：

```powershell
chcp 65001
```

---

## 📂 项目结构

```
Comfyui-Wenyi-demo1/
├── __init__.py              # 节点注册入口
├── nodes.py                 # 4 个 HappyHorse 节点定义
├── utils.py                 # OSS 上传、DashScope 轮询、VIDEO UI 构造、降级逻辑工具
├── config.json              # API Key / OSS 凭证（本地配置，勿提交公库）
├── requirements.txt         # Python 依赖清单
├── example_workflows/       # 4 个测试工作流 JSON
│   ├── test_t2v.json
│   ├── test_i2v.json
│   ├── test_r2v.json
│   └── test_video_edit.json
└── tests/                   # HTTP API 端到端测试脚本
    └── test_t2v_api.py
```

---

## 🧩 技术要点

- **VIDEO 类型**：使用 ComfyUI 0.3.30+ / 0.20+ 的 `comfy_api.input_impl.VideoFromFile`，低版本自动降级为 None
- **UI 内嵌播放**：节点返回 `{"ui": {"gifs": [...], "text": [...]}, "result": (...)}`，依靠 `ui.gifs` 协议触发播放器
- **异步任务轮询**：DashScope 异步接口 → `POST /video-synthesis` 拿 `task_id` → `GET /tasks/{id}` 轮询 → 下载 mp4 到 `output/happyhorse/`
- **OSS 配置解析**：`resolve_oss_config(ak, sk, bucket, endpoint)` 统一处理"节点覆盖 / config 默认 / 写回"逻辑，四节点共用
- **OUTPUT_NODE = True**：所有节点都标记为输出节点，无需连接下游即可触发执行并显示预览

---

## 📄 许可

本项目仅供学习与集成参考。使用阿里百炼 HappyHorse 服务时请遵守其服务协议。
