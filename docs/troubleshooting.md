# AutoVision-AI 排错指南

## 后端无法启动

- 检查是否已执行 `pip install -r requirements.txt`
- 检查 `.env` 是否存在
- 检查当前目录是否为 `backend/`

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

- 输出不是 JSON：先检查 Prompt，再检查解析器
- Comfy 任务无输出：先检查 workflow title，再查 `/history`
- 视频无法生成：先确认是否已有锁定首帧
