# AutoVision-AI

基于本地单机单显卡的漫剧/短剧自动化生产引擎骨架项目。

## 当前状态

当前仓库已生成 `V1.0` 的初始源码骨架，包含：

- `backend/`：FastAPI、SQLite、基础模型、最小路由、上传接口、媒体静态挂载

- `frontend/`：Vue 3 工作台入口、五步页面骨架、Pinia store、轮询与通知容器

- `docs/`：联调清单与后续开发入口

## 目录说明

- `backend/`

- `frontend/`

- `docs/`

## 后端启动

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
bash scripts/init_storage.sh
bash scripts/dev.sh
```

## 前端启动

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

- 如果需要正式导出成片，请提前安装并配置好 `FFmpeg`，并确保 `ffmpeg` 已加入 `PATH`

## 当前已落地的骨架能力

- 项目创建与查询

- 任务列表查询

- Mask 上传接口

- SQLite 自动建表

- `/media` 静态目录挂载

- Vue 五步工作台页面骨架

- 全局轮询与通知容器

## 下一步推荐

- 先完善 `backend/app/services` 与 `workers`

- 再把 `frontend/src/views/workbench` 中的占位页面接到真实 API

- 最后补齐 `ComfyUI / Ollama / FFmpeg / TTS` 的真实 adapter

