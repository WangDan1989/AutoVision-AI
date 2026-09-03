# AutoVision-AI

基于本地单机、单显卡、严格串行流程的漫剧/短剧自动化生产引擎。

当前版本已经不是纯骨架，`Step 1 ~ Step 5` 已接入真实本地服务链路：

- `Step 1`：调用 `Ollama` 拆解剧本并落库分镜

- `Step 2`：重建资产池并保存角色/场景绑定

- `Step 3`：调用 `ComfyUI` 生成首帧并锁帧

- `Step 4`：基于锁定首帧用 `FFmpeg` 生成真实视频片段，并用 `edge-tts` 或本地 HTTP TTS 生成音频

- `Step 5`：按分镜顺序导出成片，支持基础淡入淡出转场和字幕烧录

## 目录说明

- `backend/`：FastAPI、SQLite、真实服务接入、媒体导出链路

- `frontend/`：Vue 3 五步工作台、真实表单、预览与导出页面

- `docs/`：联调与排错文档

## Linux / macOS 后端启动

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
bash scripts/init_storage.sh
bash scripts/dev.sh
```

## Linux / macOS 前端启动

```bash
cd frontend
npm install
npm run dev
```

## Windows 启动与编译

### 后端启动（PowerShell）

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
New-Item -ItemType Directory -Force -Path storage\images, storage\videos, storage\audio, storage\exports, storage\loras, storage\temp
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 前端开发启动（PowerShell）

```powershell
cd frontend
npm install
npm run dev
```

### 前端编译打包（PowerShell）

```powershell
cd frontend
npm install
npm run build
```

编译完成后，前端产物默认输出到 `frontend/dist/`。

### Windows 使用说明

- 如果 PowerShell 禁止执行脚本，可先运行 `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

- 如果 `python` 命令不可用，可改用 `py`

- 后端在 Windows 下不依赖 `bash scripts/*.sh`，直接使用上面的 PowerShell 命令即可

- 如果需要正式导出成片，请提前安装并配置好 `FFmpeg`，并确保 `ffmpeg` 与 `ffprobe` 已加入 `PATH`

- 如果使用默认语音方案，请确保 `edge-tts` 可正常安装并可联网访问微软 TTS 服务

## 运行前置

### Step 1

- 本地启动 `Ollama`

- 在 `backend/.env` 中配置：

  - `OLLAMA_BASE_URL`

  - `OLLAMA_MODEL`

### Step 3

- 本地启动 `ComfyUI`

- 在 `backend/.env` 中配置：

  - `COMFYUI_BASE_URL`

  - `COMFYUI_CHECKPOINT`

### Step 4

- 安装 `FFmpeg`

- 默认使用：

  - `TTS_PROVIDER=edge_tts`

  - `TTS_VOICE=zh-CN-XiaoxiaoNeural`

- 如果你有本地 HTTP TTS：

```env
TTS_PROVIDER=http
TTS_BASE_URL=http://127.0.0.1:5000/tts
```

### Step 5

- 若开启字幕烧录，`FFmpeg` 需要支持 `subtitles` 过滤器，常见发行版通常自带 `libass`

- 若开启转场，系统会按 `EXPORT_TRANSITION_SEC` 做相邻片段淡入淡出

## 关键环境变量

```env
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=qwen2.5:14b

COMFYUI_BASE_URL=http://127.0.0.1:8188
COMFYUI_CHECKPOINT=

TTS_PROVIDER=edge_tts
TTS_BASE_URL=
TTS_VOICE=zh-CN-XiaoxiaoNeural

FFMPEG_BIN=ffmpeg
DEFAULT_VIDEO_DURATION_SEC=3
EXPORT_TRANSITION_SEC=0.35
```

## 当前已落地能力

- 项目创建与查询

- 剧本拆解与分镜落库

- 资产重建与绑定保存

- 首帧生成与锁帧

- 片段视频生成

- 分镜音频生成

- 成片导出

- 字幕烧录

- 基础转场导出

- 任务列表与错误回看

- `/media` 静态挂载与前端预览

## 当前限制

- 目前视频片段仍基于单张锁帧做镜头运动，不是 Comfy 原生视频工作流

- 转场目前为统一淡入淡出，不支持每段自定义

- 字幕目前按分镜台词/旁白自动生成，尚未提供逐句时间轴编辑

