# AutoVision-AI 排错指南

## 后端无法启动

- 可先执行 `python scripts/check_runtime.py` 做运行前自检
- 若后端能启动但真实依赖仍不确定，可执行 `python scripts/service_smoke_test.py`
- 后端启动后可再执行 `python scripts/smoke_test.py`，确认最小 HTTP 接口链路是否正常
- 若希望继续验证真实流水线，可执行 `python scripts/pipeline_smoke_test.py --through step1`
- 检查是否已执行 `pip install -r requirements.txt`
- 检查 `backend/.env` 是否存在
- 检查当前目录是否为 `backend/`
- 如果是 Python `3.14` 环境，`pydantic-core` 可能出现编译兼容问题，优先改用 `Python 3.11/3.12/3.13`
- 如果是旧库升级上来的 SQLite，首次启动会自动补齐 `projects.preferences_json` 列；若启动时数据库被其他进程占用，先关闭旧后端再重试
- `storage/` 目录现在会在启动时自动创建；若你手动改过 `MEDIA_ROOT`，确认该目录对当前进程可写

## 前端无法启动

- 检查是否已执行 `npm install`
- 检查 Node.js 版本是否过旧

## 媒体无法访问

- 检查 `storage/` 目录是否已创建
- 检查 `main.py` 是否已挂载 `/media`

## 上传失败

- 检查 `storage/temp` 是否存在
- 检查上传文件是否为空

## 后续接入 Ollama/ComfyUI 后常见问题

- 可先执行 `python scripts/check_runtime.py`，一次性检查 `.env`、Python 版本、FFmpeg、edge-tts、Ollama、ComfyUI`
- 可再执行 `python scripts/service_smoke_test.py`，单独确认 Ollama、ComfyUI、TTS、FFmpeg 的真实能力是否满足开跑条件
- 输出不是 JSON：先检查 Prompt，再检查解析器
- Comfy 任务无输出：先检查 `COMFYUI_CHECKPOINT`、工作流节点，再查 `/history`
- 视频无法生成：先确认是否已有锁定首帧

## Step 1 剧本拆解失败

- 若提示无法连接 `Ollama`，确认本机已启动 `ollama serve`，并检查 `OLLAMA_BASE_URL`
- 若提示模型接口异常，确认 `OLLAMA_MODEL` 已存在，可先执行 `ollama list`
- 若提示调用超时，优先检查模型是否首次加载，必要时调大 `OLLAMA_TIMEOUT_SEC`
- 若返回内容不是 JSON，先尝试换更稳定的本地模型，再重试拆解

## Step 3 首帧生成失败

- 若提示未配置 `COMFYUI_CHECKPOINT`，先在 `backend/.env` 中补齐
- 若提示无法连接 `ComfyUI`，确认本机已启动 Web 服务并检查 `COMFYUI_BASE_URL`
- 若提示等待 `ComfyUI` 响应超时，先确认模型是否仍在加载，或当前出图队列是否阻塞
- 若提示接口返回异常，先检查 ComfyUI 工作流节点、checkpoint 名称和 LoRA 文件是否存在

## Step 4 视频生成失败

- 先看工作台 `Step 4` 分镜卡片中的“最近视频失败”
- 同时看分镜卡片中的“视频任务”状态与时间，确认是不是刚刚失败还是旧失败
- 若报“当前分镜还没有锁定首帧”，先回到 `Step 3` 锁定首帧
- 若报“锁定首帧文件不存在”，说明图片文件已被删除或移动，先回到 `Step 3` 重新生成并锁定首帧
- 若报“未找到 FFmpeg 可执行文件”，先检查 `FFMPEG_BIN` 或确认 `ffmpeg` 已加入 `PATH`
- 若报 `FFmpeg 生成视频失败`，先执行 `ffmpeg -version`
- 若本地是 Windows，确认 `ffmpeg.exe` 已加入 `PATH`，或在 `.env` 中显式配置 `FFMPEG_BIN`

## Step 4 音频生成失败

- 先看工作台 `Step 4` 分镜卡片中的“最近音频失败”
- 同时看分镜卡片中的“音频任务”状态与时间，确认是不是当前配置导致的新失败
- 如果使用 `edge-tts`，确认本机可联网
- 如果使用 HTTP TTS，确认 `TTS_PROVIDER=http` 且 `TTS_BASE_URL` 可访问
- 若报“无法连接 HTTP TTS 服务”，优先检查本地 TTS 服务监听地址是否与 `TTS_BASE_URL` 一致
- 若报“HTTP TTS 接口返回异常”，检查该服务需要的鉴权、字段名和响应格式
- 若报 `edge-tts 生成音频失败`，先执行 `edge-tts --list-voices` 或确认当前网络可访问微软 TTS
- 若提示“当前分镜没有可用于 TTS 的文本”，先填写台词、旁白或 Step 4 文本框

## Step 4 批量任务异常

- 批量视频只会处理已锁定首帧的分镜
- 批量音频只会处理存在可用文本的分镜
- 批量任务为严格串行；若中途失败，可根据卡片上的失败原因逐个修复后重试
- 最近一轮批量失败明细会保留在 `Step 4` 顶部，可直接定位失败分镜
- 若你修改过项目默认参数但分镜卡片仍是旧值，可点击“应用默认值到全部分镜”

## Step 5 导出失败

- 若报“当前项目还没有分镜，无法导出”，先完成 Step 1 剧本拆解
- 若报“分镜 #X 还没有可导出的视频片段”，先回到 Step 4 为该分镜生成视频
- 若报“未找到 FFmpeg 可执行文件”，先检查 `FFMPEG_BIN` 或确认 `ffmpeg` 已加入 `PATH`
- 若字幕烧录失败，先执行 `ffmpeg -filters | grep subtitles`
- 若转场失败，检查所有分镜是否都已有视频片段
- 若页面导出预检存在错误，必须先修复再导出
- 若希望沿用上一次的导出配置，可先点“载入最近导出方案”或“按最近方案重导”
- 若只是缺少部分视频/音频，可直接用“ 一键补齐素材并导出 ”补齐后再出片
