# AutoVision-AI Demo 快速启动

这份文档面向第一次接触项目的用户，目标是先把项目界面和示例数据跑起来，再逐步接入 `Ollama`、`ComfyUI`、`FFmpeg` 和 TTS。

## 你能先跑到什么程度

- 项目中心可打开
- 五步工作台可切换
- 示例项目会自带：
  - 3 个分镜
  - 4 个资产
  - 3 张首帧占位图
  - 3 条占位音频
- 如果本机已安装 `FFmpeg`，示例脚本还会自动生成 3 段彩色占位视频

## 后端启动

### Windows

```powershell
cd backend
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
python scripts\seed_demo_project.py
start_backend.bat
```

### Linux / macOS

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python scripts/seed_demo_project.py
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

## 前端启动

### Windows

```powershell
cd frontend
npm install
start_frontend.bat
```

### Linux / macOS

```bash
cd frontend
npm install
npm run dev
```

## 进入示例项目

- 打开浏览器访问 `http://127.0.0.1:5173`
- 进入项目中心
- 找到 `AutoVision 离线示例项目`
- 点击进入工作台

## 推荐查看顺序

1. `Step 1` 看已经拆好的分镜
2. `Step 2` 看角色、场景和道具占位资产
3. `Step 3` 看已锁定的首帧占位图
4. `Step 4` 看占位音频；若本机装了 `FFmpeg`，还能看到占位视频
5. `Step 5` 先熟悉导出参数，不建议把 demo 当成正式成片结果

## 什么时候再接真实 AI 服务

- 想验证剧本拆解：接 `Ollama`
- 想验证首帧出图：接 `ComfyUI`
- 想验证真实配音：配置 `edge-tts` 或 HTTP TTS
- 想验证片段视频与导出：安装 `FFmpeg`

## 常见提示

- `seed_demo_project.py` 默认会清掉旧的同名 demo 再重建
- 如果你只想追加而不重建，可执行：

```bash
python scripts/seed_demo_project.py --no-reset
```

- 若示例项目里没有视频，通常说明当前环境里没有可用的 `ffmpeg`
- 示例项目的图片和音频都在 `backend/storage/` 下
