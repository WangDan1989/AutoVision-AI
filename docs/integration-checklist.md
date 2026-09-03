# AutoVision-AI 联调清单

## 基础连通

- [ ] `backend` 可正常启动
- [ ] `frontend` 可正常启动
- [ ] `GET /healthz` 返回 `ok`
- [ ] `/media/...` 能访问静态资源

## 数据层

- [ ] SQLite 文件自动创建
- [ ] `projects` 表可写入
- [ ] `task_queue` 表可查询

## 工作台

- [ ] 工作台首页可打开
- [ ] 五步页面可切换
- [ ] Toast 容器正常显示
- [ ] 失败任务区正常渲染

## 上传

- [ ] Mask 上传接口可成功写入 `storage/temp`
- [ ] 返回 `abs_path` 与 `relative_path`

## 后续真实能力接入

- [ ] Ollama 剧本拆解
- [ ] ComfyUI 首帧生成
- [ ] 视频工作流
- [ ] TTS 音频
- [ ] FFmpeg 合成导出
