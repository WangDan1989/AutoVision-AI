# AutoVision-AI

基于本地单机、单显卡、严格串行流程的漫剧/短剧自动化生产引擎。

当前版本已经不是纯骨架，`Step 1 ~ Step 5` 已接入真实本地服务链路：

- `Step 1`：调用 `Ollama` 拆解剧本并落库分镜

- `Step 2`：重建资产池并保存角色/场景绑定

- `Step 3`：调用 `ComfyUI` 生成首帧并锁帧

- `Step 4`：基于锁定首帧用 `FFmpeg` 生成真实视频片段，并用 `edge-tts` 或本地 HTTP TTS 生成音频

- `Step 5`：按分镜顺序导出成片，支持基础淡入淡出转场和字幕烧录

最近又补齐了两块工作台能力：

- `Step 4` 支持批量生成全部视频、批量生成全部音频

- `Step 4` 支持显示最近一次视频/TTS 任务状态与时间

- `Step 4` 支持保留最近一轮批量失败汇总

- `Step 3 ~ Step 5` 支持项目级参数持久化与页面自动回填

- `Step 5` 支持查看每次导出的 compose plan 摘要

- 前端新增“项目中心”页面，支持创建项目、进入工作台、删除项目

- `Step 5` 支持载入最近一次导出方案并重新导出

- `Step 5` 支持一键补齐缺失视频/音频并导出

## 目录说明

- `backend/`：FastAPI、SQLite、真实服务接入、媒体导出链路

- `frontend/`：Vue 3 五步工作台、真实表单、预览与导出页面

- `docs/`：联调与排错文档

## Linux / macOS 后端启动

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
bash scripts/init_storage.sh
bash scripts/dev.sh
```

- 建议使用 `Python 3.11/3.12/3.13`

- 当前不建议直接使用 `Python 3.14` 运行后端，部分依赖在该版本下可能安装失败

- 启动前可先执行运行时自检：

```bash
python scripts/check_runtime.py
```

- 后端启动后可再执行最小接口冒烟测试：

```bash
python scripts/smoke_test.py
```

- 如需自动回收测试项目，可附加：

```bash
python scripts/smoke_test.py --cleanup
```

- 如果需要进一步验证真实依赖本身，可执行服务级 smoke test：

```bash
python scripts/service_smoke_test.py
```

- 如果需要验证最小真实流水线，可执行：

```bash
python scripts/pipeline_smoke_test.py --through step1
```

- 若只想先验证后端创建项目与基础数据链路，可执行：

```bash
python scripts/pipeline_smoke_test.py --through project
```

- 以上两个脚本都支持：
  `--prefix` 自定义测试项目名前缀
  `--cleanup` 测试结束后自动删除测试项目
  `--keep-project` 即使带了 `--cleanup` 也保留测试项目

- 如果想按前缀批量清理历史测试项目，可执行：

```bash
python scripts/cleanup_test_projects.py --dry-run
python scripts/cleanup_test_projects.py --prefix smoke --prefix pipeline-smoke
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
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
New-Item -ItemType Directory -Force -Path storage\images, storage\videos, storage\audio, storage\exports, storage\loras, storage\temp
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

- 启动前可先执行运行时自检：

```powershell
python scripts/check_runtime.py
```

- 后端启动后可再执行最小接口冒烟测试：

```powershell
python scripts/smoke_test.py
```

- 如需自动回收测试项目，可附加：

```powershell
python scripts/smoke_test.py --cleanup
```

- 如果需要进一步验证真实依赖本身，可执行服务级 smoke test：

```powershell
python scripts/service_smoke_test.py
```

- 如果需要验证最小真实流水线，可执行：

```powershell
python scripts/pipeline_smoke_test.py --through step1
```

- 若只想先验证后端创建项目与基础数据链路，可执行：

```powershell
python scripts/pipeline_smoke_test.py --through project
```

- 以上两个脚本都支持：
  `--prefix` 自定义测试项目名前缀
  `--cleanup` 测试结束后自动删除测试项目
  `--keep-project` 即使带了 `--cleanup` 也保留测试项目

- 如果想按前缀批量清理历史测试项目，可执行：

```powershell
python scripts/cleanup_test_projects.py --dry-run
python scripts/cleanup_test_projects.py --prefix smoke --prefix pipeline-smoke
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

- 如果本机同时装有多个 Python，请优先使用 `3.12` 或 `3.13`

## 运行前置

### Step 1

- 本地启动 `Ollama`

- 在 `backend/.env` 中配置：

  - `OLLAMA_BASE_URL`

  - `OLLAMA_MODEL`

- 若页面提示无法连接 `Ollama`，优先检查 `OLLAMA_BASE_URL` 和 `ollama serve`

### Step 3

- 本地启动 `ComfyUI`

- 在 `backend/.env` 中配置：

  - `COMFYUI_BASE_URL`

  - `COMFYUI_CHECKPOINT`

- `COMFYUI_CHECKPOINT` 不能为空，否则 Step 3 会直接拒绝真实生成

- 若页面提示无法连接 `ComfyUI`，优先检查 `COMFYUI_BASE_URL`、ComfyUI Web 服务和模型是否加载完成

### Step 4

- 安装 `FFmpeg`

- 建议同时确认 `ffprobe` 也已加入 `PATH`

- 默认使用：

  - `TTS_PROVIDER=edge_tts`

  - `TTS_VOICE=zh-CN-XiaoxiaoNeural`

- 如果你有本地 HTTP TTS：

```env
TTS_PROVIDER=http
TTS_BASE_URL=http://127.0.0.1:5000/tts
```

- 若使用 `edge-tts`，本机需要可联网

- 成功标准：

  - 至少一个已锁定首帧的分镜可成功生成视频片段

  - 至少一个有文本的分镜可成功生成音频

### Step 5

- 若开启字幕烧录，`FFmpeg` 需要支持 `subtitles` 过滤器，常见发行版通常自带 `libass`

- 若开启转场，系统会按 `EXPORT_TRANSITION_SEC` 做相邻片段淡入淡出

- 成功标准：

  - 所有待导出分镜都已有视频片段

  - 导出预检无错误项

  - 可输出最终成片，且在需要时完成字幕烧录与转场

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

- Step 4 批量视频生成

- Step 4 批量音频生成

- Step 4 分镜级失败原因回显

- Step 4 最近任务状态与时间显示

- Step 4 批量失败汇总

- Step 3 项目级首帧参数记忆

- Step 4 项目级默认视频/TTS 参数记忆

- Step 5 compose plan 摘要展示

- Step 5 最近方案重导

- Step 5 一键补齐素材并导出

- Step 5 项目级导出开关记忆

- 成片导出

- 字幕烧录

- 基础转场导出

- 任务列表与错误回看

- `/media` 静态挂载与前端预览

## 当前限制

- 目前视频片段仍基于单张锁帧做镜头运动，不是 Comfy 原生视频工作流

- 转场目前为统一淡入淡出，不支持每段自定义

- 字幕目前支持分镜级时间轴编辑，但还不是逐句逐字级别

