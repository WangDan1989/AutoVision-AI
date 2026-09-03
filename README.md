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
