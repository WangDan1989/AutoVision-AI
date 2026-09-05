# Step 2 五维一致性规范落地 - Implementation Plan

## Task 1: 数据层扩展（SQLite ALTER + Pydantic Schema + 模型列）
- **Status**: `pending`
- **Priority**: high
- **Depends On**: None
- **Description**:
  - `backend/app/db/models/asset.py`:
    - `Asset` 新增 TEXT 列 `consistency_config_json Mapped[str] default='{}' nullable=False`（flat keys，避免嵌套空对象崩溃）
    - `AssetPreview` 新增 3 个 TEXT 列：`camera_tag / pose_tag / lighting_tag`，每个 default='' nullable=False（UQ 不受影响）
  - `backend/main.py ensure_runtime_columns()`: 对应 assets 和 asset_previews 表 4 列 ALTER 兜底，与 projects 三列写法保持一致，PRAGMA 先检查是否列存在再 ADD COLUMN
  - `backend/app/schemas/asset.py`:
    - 新增 `ConsistencyConfig(BaseModel)`，字段=16个 flat key 覆盖 5 维，`model_config = ConfigDict(extra='ignore')` 防向后兼容
    - `BindingRequest` 保留不改动；新增 `SaveConsistencyRequest(BaseModel)` 字段=ConsistencyConfig + 每张 preview 的 3 tag 覆盖（asset_preview_camera_tags: dict[role, str] 等）
  - Python dict 与 JSON 互转 util 复用现有 json.loads/dumps（asset_service.save_binding 已在用）
- **Acceptance Criteria Addressed**: AC-1, AC-4, AC-7
- **Test Requirements**:
  - `rule` TR-1.1: 重启 uvicorn 后 lifespwn 日志无 SQL error；autovision.db sqlite3 `PRAGMA table_info(assets)` 和 `PRAGMA table_info(asset_previews)` 分别返回 4/3 新列
  - `rule` TR-1.2: 手动在空字段 project 模拟旧库（consistency_config_json=NULL，用 sqlite3 update）后 list_assets 返回 consistency_config 所有 key 都有默认值，无 KeyError
- **Notes**: 用 flat JSON 降低嵌套 key missing 风险；3 preview 新 tag 不参与 UQ，仅附加元数据

## Task 2: asset_service 一致性读写 + Prompt/Neg/Seed 驱动注入
- **Status**: `pending`
- **Priority**: high
- **Depends On**: Task 1
- **Description**:
  - `asset_service.py`:
    - 新增静态方法 `_load_consistency(asset: Asset) -> ConsistencyConfig dict`，兜底 NULL=''='{}'
    - `save_consistency(asset: Asset, req: SaveConsistencyRequest) -> Asset`：写 consistency_config_json + 遍历 req.asset_preview_camera_tags 更新 AssetPreview 对应行 3 tag；asset.updated_at 刷新
    - `_build_preview_plan / _build_character_cover_prompt / _build_scene_cover_prompt / _build_prop_cover_prompt`：**第 2 位参数 style_terms 后加 consistency dict**
      - 角色 FR-1：consistency.lock_outfit=True → Prompt 末尾追加 `, consistent identical outfit design, NO outfit variations`；Negative 额外追加 `random accessories, gradient dye outfit, different clothing, wardrobe change`；特征 face_tags 拼到 Prompt 前缀
      - 场景 FR-3：consistency.scene_anchor_desc 拼到 Prompt 细节；lighting_preset + color_temp_k + light_direction → 每 3 张 preview 都追加固定光影词，lighting_tag 同步写 preview.lighting_tag
    - `_render_cover / _render_preview / rebuild_assets`：从资产读 consistency 透传各 prompt 构造函数
    - `list_assets` 输出：每个资产新增键 `consistency_config = _load_consistency(asset)` dict；每张 preview 输出额外 `camera_tag / pose_tag / lighting_tag` 3 字段；封面附加 `production_log = {seed_hash_prefix, sampler, steps, cfg}` 从 Asset.previews 第一脚 prompt_text 或静态值（sampler=euler / steps=24 / cfg=7 从 comfyui_service._build_workflow 读取当前配置）
- **Acceptance Criteria Addressed**: AC-2, AC-3, AC-4, AC-5, AC-7
- **Test Requirements**:
  - `rule` TR-2.1: 勾选 lock_outfit=True 后 rebuild → list_assets JSON 中该角色 4 预览 prompt_text 包含 "consistent identical outfit" 且 negative 包含 "random accessories"
  - `rule` TR-2.2: lighting_preset=SUNSET_GOLDEN color_temp_k=2700K 后 rebuild → 场景 3 预览 prompt_text 都含 "sunset golden hour lighting" 和 "2700K"；每张 preview.lighting_tag 非空
  - `rubric` TR-2.3: Prompt 注入干净度（无中文残留、无标点错乱）scale 1-5；≥4 pass；证据=打印首张 preview.prompt_text 前 500 字符
- **Notes**: 所有一致性字段默认值 0/空时 **完全不注入任何额外 prompt**，保证 AC-7 零崩溃 + 零风格漂移

## Task 3: 后端 API 路由（GET/POST 解耦 save_binding vs save_consistency）
- **Status**: `pending`
- **Priority**: high
- **Depends On**: Task 2
- **Description**:
  - `backend/app/api/routes/projects.py` / 对应 projects.py（Step2 assets 路由所在文件）：
    - 保持 `POST /assets/rebuild` 和 `POST /assets/{id}/binding` 原接口不动
    - 新增 `POST /api/projects/{project_id}/assets/{asset_id}/consistency`，体=SaveConsistencyRequest schema；内部调 asset_service.save_consistency + 事务 commit
    - list_assets 路由不变（服务层已返回 consistency_config）
  - `frontend/src/api/projectWorkbench.ts`:
    - 新增 `saveAssetConsistency(assetId: string, data: ConsistencyConfigTS)` axios 函数
- **Acceptance Criteria Addressed**: AC-1, AC-4
- **Test Requirements**:
  - `rule` TR-3.1: PowerShell POST `{"lock_outfit": true, "face_tags": ["tear mole"], "lighting_preset": ...}` 后 HTTP 200；GET list_assets 返回 consistency_config 同值 deep equal
  - `rule` TR-3.2: GET 正常 assets 接口不报错（无 500）
- **Notes**: 路由文件先通过 Grep 精确定位 projects.py，避免改到错文件

## Task 4: 前端 Step2AssetsView.vue UI 完整改造（2 子 Tab + 5 维面板 + 一致性徽章）
- **Status**: `pending`
- **Priority**: high
- **Depends On**: Task 3
- **Description**:
  - `frontend/src/views/workbench/Step2AssetsView.vue`:
    - TypeScript `interface ConsistencyConfigTS` 16 字段 + preview_tags 字段
    - 每个资产卡片：封面下面的表单区由单 Tab（绑定模式）改为 3 Tab：「🔗 IP-Adapter/LoRA 绑定」（保留现有绑定表单）/「🔒 一致性配置」（新）/「🧾 制作日志」（production_log 只读）
    - 一致性配置 Tab 内按 5 维分 collapse：
      1. 角色形象（仅 CHARACTER 显示）：三视图 badge（FRONT_FULL/TURN_FRONT 高亮）/ face_tags chip 输入 / lock_outfit switch / 3 格 Ref Image 上传（走现有 uploadMaskFile 通路 + 写 consistency.ref_images）
      2. 视觉画风（全类型）：底模只读 + 风格 LoRA 下拉 / 统一风格附加词 textarea / 统一 Negative 只读 code block
      3. 场景空间（仅 SCENE）：主相机 tag chip / scene_anchor_desc textarea / 2 格底图上传
      4. 镜头语言（CHARACTER/SCENE）：每个预览位动作 tag 编辑 / 运镜下拉枚举 / 180 轴标记
      5. 影调布光（全类型，SCENE 优先）：主光源 preset 下拉 / 色温 slider / 方向 radio / LUT tag / voice_preset CHARACTER 音色
    - 标题行右侧加 Consistency Score 徽章：算法=5 维度中「非空率 ≥ 60%」每维度 1 分；分数映射 0-1 红 / 2-3 黄 / 4-5 绿
    - 一致性配置表单新增独立「保存一致性配置」按钮，走 saveAssetConsistency API；与「保存绑定」按钮并列
- **Acceptance Criteria Addressed**: AC-1, AC-6, AC-7
- **Test Requirements**:
  - `rule` TR-4.1: browser_snapshot 人物卡 + 场景卡 + 道具卡一致性配置 Tab 打开后，5 维 collapse 标题 DOM 出现（分别定位 heading）
  - `rubric` TR-4.2: UI 可用性/可辨识性；scale 1-5；≥4 pass；锚 1=布局混乱、3=可用但拥挤、5=分区清晰 badge 一眼可见；证据=3 张 Tab screenshot（character/scene/prop）
  - `rule` TR-4.3: 徽章颜色/数字与字段非空严格匹配；browser_evaluate 读取 3 资产卡 score 数字与其 5 维字段非空一致

## Task 5: 端到端回归（真实 rebuild + 浏览器 + TS 构建验证）
- **Status**: `pending`
- **Priority**: high
- **Depends On**: Task 4
- **Description**:
  - 流程：
    1. FastAPI 重启 + 应用新 ALTER
    2. 给凌风 CHARACTER 写 lock_outfit=true + face_tags tear mole jade hairpin + 发 azue-blue robe；给下山路 SCENE 填 lighting_preset=SUNSET_GOLDEN 色温 2700K 方向 side_left；POST save_consistency（分别 HTTP 200）
    3. POST rebuild_assets(PID=c5eeb67c) → 等待 7 covers + 22 previews 全部 COMPLETED
    4. 校验 list_assets JSON（AC-2/AC-3 rule 条件全满足）
    5. 浏览器截图 3 Tab（人物/场景/道具）+ 一致性配置 Tab 展开截图；徽章颜色 DOM evaluate 校验
    6. `cd frontend; npm run build` 确认 TS 零错误
    7. 清理 debug 脚本
- **Acceptance Criteria Addressed**: AC-2, AC-3, AC-5, AC-6, AC-7
- **Test Requirements**:
  - `rule` TR-5.1: 7/7 covers + 22/22 previews 100% COMPLETED
  - `rule` TR-5.2: npm run build exit code 0，无 TS/Scoped CSS 报错
  - `rubric` TR-5.3: 实际缩略图主观一致性；scale 1-5；≥4 pass；锚 1=凌风 4 张 4 种色衣服、3=2 张主色一致小变、5=4 张主色+配饰 100% 一致+脸型一致
  - `rule` TR-5.4: 场景 3 张光影色调肉眼连续（下山路 3 张金黄暖调；窗前 3 张黄昏暖光）
- **Notes**: 这是最终验收，截图归档供用户查看
